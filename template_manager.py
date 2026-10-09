# template_manager.py
# Mockup Template Manager - zoomable/pannable preview with Rectangle + Free modes
# and optional pixel-grid snapping. Quads composited with PIL; preview written to a
# file-backed PNG because Tk on this machine renders JPEG pixel data as grey.

import os
import json
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw

import mockup_generator
from mockup_generator import MOCKUP_CONFIG_FILE

CORNER_LABELS = ["Top-Left", "Top-Right", "Bottom-Right", "Bottom-Left"]

VIEW_W = 1300
VIEW_H = 880
MAX_SCALE = 4.0
ZOOM_STEP = 1.25
PAN_STEP = 30
BG = "#1a1a1a"


class TemplateManager(tk.Toplevel):
    def __init__(self, master, on_apply_callback=None):
        super().__init__(master)
        self.master = master
        self.on_apply_callback = on_apply_callback

        self.title("Mockup Template Manager")
        self.geometry("1150x780")
        self.geometry("1800x1300")
        self.configure(bg="#2b2b2b")

        self.templates = json.loads(json.dumps(mockup_generator.MOCKUP_CONFIGS))
        self.current_name = None
        self.current_image_path = None
        self.points = {
            "landscape": [[0, 0], [0, 0], [0, 0], [0, 0]],
            "portrait":  [[0, 0], [0, 0], [0, 0], [0, 0]]
        }
        # Per-orientation progress in Rectangle mode: "empty" | "tl" | "done"
        self.rect_state = {"landscape": "empty", "portrait": "empty"}
        self.current_corner = 0

        self.full_image = None
        self.orig_size = (0, 0)
        self.min_scale = 0.05
        self.scale = 1.0
        self.view_x = 0.0
        self.view_y = 0.0
        self.tk_photo = None
        self._pan_last = None

        self._build_ui()
        self._refresh_list()
        first = list(self.templates.keys())
        if first:
            self._select_template(first[0])
        self.grab_set()

    # ── UI ─────────────────────────────────────────────────────────
    def _build_ui(self):
        left = tk.Frame(self, bg="#3a3a3a", width=200)
        left.pack(side="left", fill="y", padx=10, pady=10)
        left.pack_propagate(False)

        tk.Label(left, text="Templates", font=("Arial", 14, "bold"),
                 bg="#3a3a3a", fg="white").pack(pady=(10, 5), padx=10, anchor="w")

        self.list_frame = tk.Frame(left, bg="#3a3a3a")
        self.list_frame.pack(fill="both", expand=True, padx=10, pady=5)

        btns = tk.Frame(left, bg="#3a3a3a")
        btns.pack(fill="x", padx=10, pady=(0, 10))
        tk.Button(btns, text="New", command=self._new_template, bg="#4a4a4a",
                  fg="white", relief="flat", padx=10, pady=4).pack(side="left", padx=2)
        tk.Button(btns, text="Delete", command=self._delete_template, bg="#932919",
                  fg="white", relief="flat", padx=10, pady=4).pack(side="left", padx=2)

        right = tk.Frame(self, bg="#2b2b2b")
        right.pack(side="left", fill="both", expand=True, padx=(0, 10), pady=10)

        top_frame = tk.Frame(right, bg="#2b2b2b")
        top_frame.pack(fill="x", padx=10, pady=(10, 5))
        tk.Label(top_frame, text="Name:", bg="#2b2b2b", fg="white").pack(side="left")
        self.name_entry = tk.Entry(top_frame, width=25, bg="#4a4a4a", fg="white", insertbackground="white")
        self.name_entry.pack(side="left", padx=5)
        tk.Label(top_frame, text="  Image:", bg="#2b2b2b", fg="white").pack(side="left")
        self.image_entry = tk.Entry(top_frame, width=40, bg="#4a4a4a", fg="white", insertbackground="white")
        self.image_entry.pack(side="left", padx=5)
        tk.Button(top_frame, text="Browse", command=self._browse_image, bg="#4a4a4a",
                  fg="white", relief="flat", padx=8).pack(side="left")

        self.orient_info = tk.Label(right, text="No image loaded", bg="#2b2b2b", fg="#aaa")
        self.orient_info.pack(anchor="e", padx=10)

        # Mode + snap toolbar
        modebar = tk.Frame(right, bg="#2b2b2b")
        modebar.pack(fill="x", padx=10, pady=(0, 4))
        tk.Label(modebar, text="Draw mode:", bg="#2b2b2b", fg="white").pack(side="left", padx=(0, 4))
        self.mode_var = tk.StringVar(value="rect")
        tk.Radiobutton(modebar, text="Rectangle (2 clicks)", variable=self.mode_var, value="rect",
                       command=self._mode_changed, bg="#2b2b2b", fg="white",
                       selectcolor="#4a4a4a").pack(side="left", padx=4)
        tk.Radiobutton(modebar, text="Free quad (4 clicks)", variable=self.mode_var, value="free",
                       command=self._mode_changed, bg="#2b2b2b", fg="white",
                       selectcolor="#4a4a4a").pack(side="left", padx=4)
        tk.Label(modebar, text="   Snap to (px):", bg="#2b2b2b", fg="white").pack(side="left", padx=(15, 4))
        self.snap_var = tk.IntVar(value=1)
        tk.Spinbox(modebar, from_=0, to=200, textvariable=self.snap_var, width=5,
                   bg="#4a4a4a", fg="white", buttonbackground="#4a4a4a",
                   insertbackground="white").pack(side="left")
        tk.Label(modebar, text="  (0 = off, 1 = pixel)", bg="#2b2b2b", fg="#777").pack(side="left")

        # Zoom toolbar
        bar = tk.Frame(right, bg="#2b2b2b")
        bar.pack(fill="x", padx=10, pady=(0, 4))
        tk.Button(bar, text="Zoom In  +", command=lambda: self._zoom(ZOOM_STEP),
                  bg="#4a4a4a", fg="white", relief="flat", padx=10, pady=3).pack(side="left", padx=2)
        tk.Button(bar, text="Zoom Out  -", command=lambda: self._zoom(1 / ZOOM_STEP),
                  bg="#4a4a4a", fg="white", relief="flat", padx=10, pady=3).pack(side="left", padx=2)
        tk.Button(bar, text="Fit", command=self._fit_view_btn,
                  bg="#4a4a4a", fg="white", relief="flat", padx=10, pady=3).pack(side="left", padx=2)
        self.zoom_label = tk.Label(bar, text="Zoom: 100%", bg="#2b2b2b", fg="#8fd")
        self.zoom_label.pack(side="left", padx=10)
        tk.Label(bar, text="  (scroll = zoom, right-drag / arrows = pan, left-click = place point)",
                 bg="#2b2b2b", fg="#777").pack(side="left")

        # Image display
        img_container = tk.Frame(right, bg=BG)
        img_container.pack(padx=10, pady=4)
        self.img_label = tk.Label(img_container, bg=BG, width=VIEW_W, height=VIEW_H, cursor="crosshair")
        self.img_label.pack()
        self.img_label.bind("<Button-1>", self._on_image_click)
        self.img_label.bind("<MouseWheel>", self._on_mouse_wheel)
        for b in ("2", "3"):
            self.img_label.bind(f"<ButtonPress-{b}>", self._on_pan_press)
            self.img_label.bind(f"<B{b}-Motion>", self._on_pan_motion)
            self.img_label.bind(f"<ButtonRelease-{b}>", self._on_pan_release)

        # Orientation toggle
        tog = tk.Frame(right, bg="#2b2b2b")
        tog.pack(fill="x", padx=10, pady=4)
        self.orient_var = tk.StringVar(value="landscape")
        tk.Radiobutton(tog, text="Landscape points", variable=self.orient_var,
                       value="landscape", command=self._orientation_changed,
                       bg="#2b2b2b", fg="white", selectcolor="#4a4a4a").pack(side="left", padx=10)
        tk.Radiobutton(tog, text="Portrait points", variable=self.orient_var,
                       value="portrait", command=self._orientation_changed,
                       bg="#2b2b2b", fg="white", selectcolor="#4a4a4a").pack(side="left", padx=10)

        # Coordinate entries
        grid = tk.Frame(right, bg="#2b2b2b")
        grid.pack(fill="x", padx=10, pady=(0, 5))
        tk.Label(grid, text="Corner", font=("Arial", 10, "bold"), bg="#2b2b2b", fg="white").grid(row=0, column=0, padx=4, sticky="w")
        tk.Label(grid, text="X", font=("Arial", 10, "bold"), bg="#2b2b2b", fg="white").grid(row=0, column=1, padx=4)
        tk.Label(grid, text="Y", font=("Arial", 10, "bold"), bg="#2b2b2b", fg="white").grid(row=0, column=2, padx=4)

        self.coord_entries = {}
        for i, label in enumerate(CORNER_LABELS):
            tk.Label(grid, text=label, font=("Arial", 10), bg="#2b2b2b", fg="white").grid(row=i + 1, column=0, padx=4, pady=1, sticky="w")
            ex = tk.Entry(grid, width=8, justify="center", bg="#4a4a4a", fg="white", insertbackground="white")
            ex.grid(row=i + 1, column=1, padx=4, pady=1)
            ey = tk.Entry(grid, width=8, justify="center", bg="#4a4a4a", fg="white", insertbackground="white")
            ey.grid(row=i + 1, column=2, padx=4, pady=1)
            ex.bind("<FocusOut>", lambda e, i=i: self._sync_entries_to_canvas())
            ey.bind("<FocusOut>", lambda e, i=i: self._sync_entries_to_canvas())
            ex.bind("<Return>", lambda e, i=i: self._sync_entries_to_canvas())
            ey.bind("<Return>", lambda e, i=i: self._sync_entries_to_canvas())
            self.coord_entries[i] = (ex, ey)

        # Bottom buttons
        bottom = tk.Frame(right, bg="#2b2b2b")
        bottom.pack(fill="x", padx=10, pady=(0, 10))
        tk.Button(bottom, text="Save This Template", command=self._save_this_template,
                  bg="#4a4a4a", fg="white", relief="flat", padx=15, pady=5).pack(side="left", padx=5)
        tk.Button(bottom, text="Apply & Close", command=self._apply_and_close,
                  bg="#2FA572", fg="white", relief="flat", padx=15, pady=5).pack(side="left", padx=5)

        self.bind_all("<Key>", self._on_key)

    # ── List ───────────────────────────────────────────────────────
    def _refresh_list(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        names = list(self.templates.keys())
        if not names:
            tk.Label(self.list_frame, text="(no templates)", bg="#3a3a3a", fg="gray").pack(pady=10)
            return
        for name in names:
            tk.Button(self.list_frame, text=name.replace('_', ' ').title(),
                      command=lambda n=name: self._select_template(n),
                      bg="#4a4a4a", fg="white", relief="flat",
                      anchor="w", padx=8, pady=3).pack(fill="x", pady=2)

    def _new_template(self):
        name = "new_template"; n = 1
        while name in self.templates:
            name = f"new_template_{n}"; n += 1
        self.templates[name] = {"template_path": "",
                                "perspective": True,
                                "position_data": {"landscape": [[0,0],[0,0],[0,0],[0,0]],
                                                  "portrait":  [[0,0],[0,0],[0,0],[0,0]]}}
        self._refresh_list()
        self._select_template(name)

    def _delete_template(self):
        if not self.current_name:
            messagebox.showinfo("Delete", "Select a template first.", parent=self); return
        if not messagebox.askyesno("Delete Template", f"Delete '{self.current_name}'?", parent=self):
            return
        del self.templates[self.current_name]
        self.current_name = None
        self._refresh_list()
        self._clear_editor()

    def _select_template(self, name):
        self._save_this_template(silent=True)
        self.current_name = name
        cfg = self.templates.get(name, {})
        self.name_entry.delete(0, "end"); self.name_entry.insert(0, name)
        self.image_entry.delete(0, "end"); self.image_entry.insert(0, cfg.get("template_path", ""))
        self.current_image_path = cfg.get("template_path", "")
        pd = cfg.get("position_data", {})
        self.points = {"landscape": pd.get("landscape", [[0,0],[0,0],[0,0],[0,0]]),
                       "portrait":  pd.get("portrait",  [[0,0],[0,0],[0,0],[0,0]])}
        # A loaded template counts as a complete quad in both modes
        for o in ("landscape", "portrait"):
            self.rect_state[o] = "done" if any(any(p) for p in self.points[o]) else "empty"
        self._load_image()
        self._populate_coord_entries()
        self._redraw()

    def _clear_editor(self):
        self.name_entry.delete(0, "end")
        self.image_entry.delete(0, "end")
        self.current_image_path = None
        self.full_image = None
        self.tk_photo = None
        self.img_label.configure(image="", text="No image loaded")
        self.orient_info.configure(text="No image loaded")
        for i in range(4):
            self.coord_entries[i][0].delete(0, "end")
            self.coord_entries[i][1].delete(0, "end")

    # ── Image loading ──────────────────────────────────────────────
    def _browse_image(self):
        path = filedialog.askopenfilename(
            title="Select Template Image",
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.bmp *.tiff"), ("All Files", "*.*")],
            parent=self)
        if not path:
            return
        self.image_entry.delete(0, "end")
        self.image_entry.insert(0, path)
        self.current_image_path = path
        self._load_image()
        self._redraw()

    def _load_image(self):
        if not self.current_image_path or not os.path.exists(self.current_image_path):
            self.full_image = None
            self.img_label.configure(image="", text="No image loaded")
            self.orient_info.configure(text="No image loaded")
            return
        try:
            img = Image.open(self.current_image_path)
            img.load()
            self.orig_size = img.size
            if img.mode != "RGB":
                img = img.convert("RGB")
            base = os.path.join(tempfile.gettempdir(), "tm_base_tmp.png")
            img.save(base, format="PNG")
            self.full_image = Image.open(base)
            self.full_image.load()
            self.min_scale = min(VIEW_W / self.orig_size[0], VIEW_H / self.orig_size[1])
            self._fit_view()
            self._update_zoom_label()
            self.orient_info.configure(text=f"Template: {self.orig_size[0]}x{self.orig_size[1]}")
            print(f"[TM] Loaded template {self.orig_size[0]}x{self.orig_size[1]}, fit scale {self.min_scale:.3f}")
        except Exception as e:
            self.full_image = None
            messagebox.showerror("Image Error", f"Could not load image:\n{e}", parent=self)

    # ── View / zoom / pan ──────────────────────────────────────────
    def _fit_view(self):
        if self.full_image is None:
            return
        w, h = self.orig_size
        self.scale = self.min_scale
        self.view_x = (w - VIEW_W / self.scale) / 2
        self.view_y = (h - VIEW_H / self.scale) / 2
        self._clamp_view()
        self._update_zoom_label()

    def _fit_view_btn(self):
        self._fit_view()
        self._redraw()

    def _clamp_view(self):
        if self.full_image is None:
            return
        w, h = self.orig_size
        self.scale = max(self.min_scale, min(MAX_SCALE, self.scale))
        vw = VIEW_W / self.scale
        vh = VIEW_H / self.scale
        self.view_x = max(0.0, min(self.view_x, w - vw))
        self.view_y = max(0.0, min(self.view_y, h - vh))

    def _zoom(self, factor, cx=None, cy=None):
        if self.full_image is None:
            return
        if cx is None:
            cx, cy = VIEW_W / 2, VIEW_H / 2
        new_scale = max(self.min_scale, min(MAX_SCALE, self.scale * factor))
        if new_scale == self.scale:
            return
        ax = self.view_x + cx / self.scale
        ay = self.view_y + cy / self.scale
        self.scale = new_scale
        self.view_x = ax - cx / self.scale
        self.view_y = ay - cy / self.scale
        self._clamp_view()
        self._update_zoom_label()
        self._redraw()

    def _pan(self, dx_screen, dy_screen):
        if self.full_image is None:
            return
        self.view_x -= dx_screen / self.scale
        self.view_y -= dy_screen / self.scale
        self._clamp_view()
        self._redraw()

    def _on_mouse_wheel(self, event):
        self._zoom(ZOOM_STEP if event.delta > 0 else 1 / ZOOM_STEP, event.x, event.y)

    def _on_pan_press(self, event):
        self._pan_last = (event.x, event.y)

    def _on_pan_motion(self, event):
        if self._pan_last is None:
            return
        lx, ly = self._pan_last
        self._pan(event.x - lx, event.y - ly)
        self._pan_last = (event.x, event.y)

    def _on_pan_release(self, event):
        self._pan_last = None

    def _on_key(self, event):
        if isinstance(self.focus_get(), tk.Entry):
            return
        d = PAN_STEP
        if event.keysym == "Left":   self._pan(-d, 0)
        elif event.keysym == "Right": self._pan(d, 0)
        elif event.keysym == "Up":    self._pan(0, -d)
        elif event.keysym == "Down":  self._pan(0, d)
        elif event.keysym in ("plus", "equal"): self._zoom(ZOOM_STEP)
        elif event.keysym == "minus": self._zoom(1 / ZOOM_STEP)
        elif event.keysym == "0":     self._fit_view_btn()

    def _update_zoom_label(self):
        self.zoom_label.configure(text=f"Zoom: {self.scale * 100:.0f}%")

    # ── Mode / orientation ─────────────────────────────────────────
    def _mode_changed(self):
        self.rect_state[self.orient_var.get()] = "empty"
        self.points[self.orient_var.get()] = [[0,0],[0,0],[0,0],[0,0]]
        self.current_corner = 0
        self._populate_coord_entries()
        self._redraw()

    def _orientation_changed(self):
        self.current_corner = 0
        self._populate_coord_entries()
        self._redraw()

    # ── Render ─────────────────────────────────────────────────────
    def _redraw(self):
        if self.full_image is None:
            self.img_label.configure(image="", text="No image loaded")
            return
        w, h = self.orig_size
        vx, vy = self.view_x, self.view_y
        vw = int(round(VIEW_W / self.scale))
        vh = int(round(VIEW_H / self.scale))

        # ── FIXED: build a canvas of exactly vw × vh image pixels ──
        # The old code cropped the image and resized the crop to
        # (VIEW_W, VIEW_H). When the image was smaller than the
        # viewport (i.e. at fit / low zoom with an aspect-ratio
        # mismatch) the crop was smaller than vw × vh, so the resize
        # stretched it non-uniformly. to_screen() then used the
        # wrong scale and the red box landed in the wrong place.
        #
        # Fix: create a canvas of exactly vw × vh, paste the visible
        # part of the image onto it at 1:1, then resize the canvas
        # to (VIEW_W, VIEW_H). The resize is now always a uniform
        # scale by self.scale, so to_screen() is correct at every
        # zoom level.
        canvas = Image.new("RGB", (vw, vh), BG)

        # Visible region of the image in image coordinates
        ix0 = max(0, int(round(vx)))
        iy0 = max(0, int(round(vy)))
        ix1 = min(w, int(round(vx)) + vw)
        iy1 = min(h, int(round(vy)) + vh)

        if ix1 > ix0 and iy1 > iy0:
            crop = self.full_image.crop((ix0, iy0, ix1, iy1))
            # Paste at 1:1 — the canvas is in image-pixel space
            canvas.paste(crop, (ix0 - int(round(vx)), iy0 - int(round(vy))))

        disp = canvas.resize((VIEW_W, VIEW_H), Image.BILINEAR)
        draw = ImageDraw.Draw(disp)

        def to_screen(x, y):
            return ((x - vx) * self.scale, (y - vy) * self.scale)

        mode = self.mode_var.get()
        for orient, color in (("landscape", "#ff4d4d"), ("portrait", "#4da6ff")):
            pts = self.points[orient]
            if mode == "rect":
                st = self.rect_state[orient]
                if st == "tl":
                    # only the first corner placed so far
                    dx, dy = to_screen(*pts[0])
                    draw.ellipse([dx - 7, dy - 7, dx + 7, dy + 7], fill=color, outline="white", width=2)
                    draw.text((dx + 10, dy - 12), "1", fill=color)
                elif st == "done":
                    disp_pts = [to_screen(x, y) for x, y in pts]
                    draw.polygon(disp_pts, outline=color, width=3)
                    for i, (dx, dy) in enumerate(disp_pts):
                        draw.ellipse([dx - 7, dy - 7, dx + 7, dy + 7], fill=color, outline="white", width=2)
                        draw.text((dx + 10, dy - 12), str(i + 1), fill=color)
            else:  # free quad
                if any((x or y) for x, y in pts):
                    disp_pts = [to_screen(x, y) for x, y in pts]
                    draw.polygon(disp_pts, outline=color, width=3)
                    for i, (dx, dy) in enumerate(disp_pts):
                        draw.ellipse([dx - 7, dy - 7, dx + 7, dy + 7], fill=color, outline="white", width=2)
                        draw.text((dx + 10, dy - 12), str(i + 1), fill=color)

        p = os.path.join(tempfile.gettempdir(), "tm_view_tmp.png")
        disp.save(p, format="PNG")
        reloaded = Image.open(p)
        reloaded.load()
        self.tk_photo = ImageTk.PhotoImage(reloaded)
        self.img_label.configure(image=self.tk_photo, text="")

    # ── Click handling ─────────────────────────────────────────────
    def _on_image_click(self, event):
        if self.full_image is None:
            messagebox.showinfo("No Image", "Load a template image first.", parent=self)
            return
        ox = self.view_x + event.x / self.scale
        oy = self.view_y + event.y / self.scale
        ox = max(0.0, min(ox, self.orig_size[0]))
        oy = max(0.0, min(oy, self.orig_size[1]))

        # Optional pixel-grid snap
        try:
            g = int(self.snap_var.get())
        except (ValueError, tk.TclError):
            g = 0
        if g > 0:
            ox = round(ox / g) * g
            oy = round(oy / g) * g
            ox = max(0, min(ox, self.orig_size[0]))
            oy = max(0, min(oy, self.orig_size[1]))

        orient = self.orient_var.get()
        if self.mode_var.get() == "rect":
            st = self.rect_state[orient]
            if st in ("empty", "done"):
                # first (or new) click = top-left
                self.points[orient] = [[round(ox), round(oy)], [0,0], [0,0], [0,0]]
                self.rect_state[orient] = "tl"
            else:  # st == "tl": second click = bottom-right -> build perfect rectangle
                tl = self.points[orient][0]
                br = [round(ox), round(oy)]
                tr = [br[0], tl[1]]
                bl = [tl[0], br[1]]
                self.points[orient] = [tl, tr, br, bl]   # TL, TR, BR, BL
                self.rect_state[orient] = "done"
        else:  # free quad
            self.points[orient][self.current_corner] = [round(ox), round(oy)]
            self.current_corner = (self.current_corner + 1) % 4

        self._populate_coord_entries()
        self._redraw()

    # ── Coordinate entries ─────────────────────────────────────────
    def _populate_coord_entries(self):
        orient = self.orient_var.get()
        for i in range(4):
            x, y = self.points[orient][i]
            ex, ey = self.coord_entries[i]
            ex.delete(0, "end"); ex.insert(0, str(x))
            ey.delete(0, "end"); ey.insert(0, str(y))

    def _sync_entries_to_canvas(self):
        orient = self.orient_var.get()
        try:
            for i in range(4):
                ex, ey = self.coord_entries[i]
                self.points[orient][i] = [int(ex.get().strip()), int(ey.get().strip())]
            if self.mode_var.get() == "rect" and any(any(p) for p in self.points[orient]):
                self.rect_state[orient] = "done"
        except ValueError:
            pass
        self._redraw()

    # ── Save ───────────────────────────────────────────────────────
    def _save_this_template(self, silent=False):
        name = self.name_entry.get().strip()
        if not name:
            if not silent:
                messagebox.showwarning("Name Required", "Please enter a template name.", parent=self)
            return
        name = name.lower().replace(" ", "_")
        self._sync_entries_to_canvas()
        entry = dict(self.templates.get(name, {}))
        entry["template_path"] = self.image_entry.get().strip()
        entry["position_data"] = {"landscape": self.points["landscape"],
                                  "portrait":  self.points["portrait"]}
        self.templates[name] = entry
        if self.current_name and self.current_name != name and self.current_name in self.templates:
            del self.templates[self.current_name]
        self.current_name = name
        self._refresh_list()



    def _apply_and_close(self):
        self._save_this_template(silent=True)
        try:
            mockup_generator.MOCKUP_CONFIGS = self.templates
            mockup_generator.save_mockup_configs()
        except Exception as e:
            messagebox.showerror("Save Error", f"Could not save configs:\n{e}", parent=self)
            return
        if self.on_apply_callback:
            self.on_apply_callback()
        self.destroy()
