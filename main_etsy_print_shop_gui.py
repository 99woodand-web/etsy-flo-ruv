# main_etsy_print_shop_gui.py  (complete, consolidated)
import os
import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image

import mockup_generator
from image_uploader_manager import is_image_file
from upscaling_resolution_tool import PRINT_SIZES_MM, upscale_image
from mockup_generator import generate_mockup, load_mockup_configs
from print_ready_exporter import export_print_ready_image
from template_manager import TemplateManager
from pinterest_pin_maker import create_pinterest_pin
from batch_processor import BatchProcessor
from listing_bundle import create_listing_bundle
from pathlib import Path


DEFAULT_DPI = 300
UPLOAD_FOLDER = "uploads"
UPSCALED_FOLDER = "upscaled_images"
MOCKUP_FOLDER = "mockup_images"
PRINT_READY_FOLDER = "print_ready_files"
SPEC_SIZES = {'A4': (210, 297), 'A3': (297, 420), 'A2': (420, 594), 'A1': (594, 841)}
PINTEREST_FOLDER = "pinterest_pins"

for _d in (UPLOAD_FOLDER, UPSCALED_FOLDER, MOCKUP_FOLDER, PRINT_READY_FOLDER, PINTEREST_FOLDER):
    os.makedirs(_d, exist_ok=True)

load_mockup_configs()


def build_spec_check_text(image_path):
    """Spec-check info for one image (from spec_check.py), with ticks for sizes already met."""
    if not image_path or not os.path.exists(image_path):
        return "(none)"
    dpi = DEFAULT_DPI

    def px(mm):
        return mm * dpi / 25.4

    try:
        with Image.open(image_path) as img:
            w, h = img.size
    except Exception as e:
        return f"Could not read image: {e}"

    orient = "landscape" if w > h else "portrait"
    size_mb = round(os.path.getsize(image_path) / 1048576, 2)
    mw = w / dpi * 25.4
    mh = h / dpi * 25.4

    lines = [
        "File:      " + os.path.basename(image_path),
        "Pixels:    " + str(w) + " x " + str(h) + "  (" + orient + ")",
        "File size: " + str(size_mb) + " MB",
        "",
        "Largest print at true 300 DPI (no upscale):",
        "  " + str(round(mw)) + " x " + str(round(mh)) + " mm",
        "",
        "Upscale needed to fill each size (300 DPI):",
        "  size   portrait   landscape",
    ]
    for name, (a, b) in SPEC_SIZES.items():
        pw, ph = px(a), px(b)
        lw, lh = px(b), px(a)
        ps = max(pw / w, ph / h)
        ls = max(lw / w, lh / h)
        pt = "  \u2713  " if ps <= 1.05 else "~" + str(round(ps, 1)) + "x"
        lt = "  \u2713  " if ls <= 1.05 else "~" + str(round(ls, 1)) + "x"
        lines.append("  " + name.ljust(5) + "  " + pt.rjust(9) + "    " + lt.rjust(9))
    return "\n".join(lines)


class EtsyPrintShopApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Etsy Print Shop - AndyW")
        self.geometry("1250x900")
        self.minsize(1050, 820)

        self.original_image_path = None
        self.upscaled_image_path = None
        self.generated_mockup_paths = []
        self.preview_images = []

        # row0 = panels, row1 = spec, row2 = status
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)

        # LEFT: scrollable so all controls + Template Manager are always reachable
        self.left_scroll = ctk.CTkScrollableFrame(self)
        self.left_scroll.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)
        self.left_scroll.grid_columnconfigure(0, weight=1)

        # RIGHT: preview
        self.right_panel = ctk.CTkFrame(self)
        self.right_panel.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)
        self.right_panel.grid_columnconfigure(0, weight=1)
        self.right_panel.grid_rowconfigure(1, weight=1)

        self._build_left_panel()
        self._build_right_panel()
        self._build_spec_panel()
        self._build_status_bar()

    # ── LEFT (inside scrollable frame) ─────────────────────────────
    def _build_left_panel(self):
        L = self.left_scroll
        ctk.CTkLabel(L, text="Etsy Print Shop", font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, pady=(10, 6), padx=10, sticky="ew")

        # 1. Upload
        up = ctk.CTkFrame(L); up.grid(row=1, column=0, sticky="ew", padx=10, pady=4)
        up.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(up, text="1. Upload Artwork", font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=0, column=0, sticky="ew", padx=10, pady=(8, 4))
        ctk.CTkButton(up, text="Select Image File", command=self._on_upload, fg_color="#2FA572", hover_color="#25805A").grid(
            row=1, column=0, sticky="", padx=10, pady=4)
        self.upload_status_label = ctk.CTkLabel(up, text="No file selected", text_color="gray", font=ctk.CTkFont(size=12))
        self.upload_status_label.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 8))

               # 2. Upscale
        uc = ctk.CTkFrame(L); uc.grid(row=2, column=0, sticky="ew", padx=10, pady=4)
        uc.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(uc, text="2. Upscale to Print Size", font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=0, column=0, sticky="ew", padx=10, pady=(8, 4))

        size_row = ctk.CTkFrame(uc, fg_color="transparent"); size_row.grid(row=1, column=0, sticky="ew", padx=10, pady=3)
        size_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(size_row, text="Size:").grid(row=0, column=0, padx=(0, 5))
        self.size_var = ctk.StringVar(value="A3")
        ctk.CTkOptionMenu(size_row, variable=self.size_var, values=list(PRINT_SIZES_MM.keys())).grid(row=0, column=1, sticky="ew")

        orient_row = ctk.CTkFrame(uc, fg_color="transparent"); orient_row.grid(row=2, column=0, sticky="ew", padx=10, pady=3)
        orient_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(orient_row, text="Orientation:").grid(row=0, column=0, padx=(0, 5))
        self.upscale_orient_var = ctk.StringVar(value="auto")
        ctk.CTkOptionMenu(orient_row, variable=self.upscale_orient_var, values=["auto", "portrait", "landscape"]).grid(row=0, column=1, sticky="ew")

        qual_row = ctk.CTkFrame(uc, fg_color="transparent"); qual_row.grid(row=3, column=0, sticky="ew", padx=10, pady=3)
        qual_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(qual_row, text="Quality:").grid(row=0, column=0, padx=(0, 5))
        self.resample_var = ctk.StringVar(value="lanczos")
        ctk.CTkOptionMenu(qual_row, variable=self.resample_var,
                  values=["bicubic", "lanczos", "realesrgan"]).grid(row=0, column=1, sticky="ew")


        fit_row = ctk.CTkFrame(uc, fg_color="transparent"); fit_row.grid(row=4, column=0, sticky="ew", padx=10, pady=3)
        fit_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(fit_row, text="Fit:").grid(row=0, column=0, padx=(0, 5))
        self.fit_var = ctk.StringVar(value="Fill & Crop (no distortion)")
        ctk.CTkOptionMenu(fit_row, variable=self.fit_var,
                          values=["Fill & Crop (no distortion)", "Stretch to fit"]).grid(row=0, column=1, sticky="ew")

        cpos_row = ctk.CTkFrame(uc, fg_color="transparent"); cpos_row.grid(row=5, column=0, sticky="ew", padx=10, pady=3)
        cpos_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(cpos_row, text="Crop Position:").grid(row=0, column=0, padx=(0, 5))
        self.crop_pos_var = ctk.StringVar(value="Center")
        ctk.CTkOptionMenu(cpos_row, variable=self.crop_pos_var,
                          values=["Center", "Top", "Bottom", "Left", "Right"]).grid(row=0, column=1, sticky="ew")

        ctk.CTkButton(uc, text="Upscale Image", command=self._on_upscale,
                      fg_color="#2FA572", hover_color="#25805A").grid(row=6, column=0, sticky="", padx=10, pady=4)



        # 3. Mockups
        mk = ctk.CTkFrame(L); mk.grid(row=3, column=0, sticky="ew", padx=10, pady=4)
        mk.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(mk, text="3. Generate Mockups", font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=0, column=0, sticky="ew", padx=10, pady=(8, 4))
        ctk.CTkLabel(mk, text="Mockup Types:", font=ctk.CTkFont(size=12)).grid(row=1, column=0, sticky="ew", padx=10, pady=(4, 2))

        self.mockup_types_frame = ctk.CTkFrame(mk, fg_color="transparent")
        self.mockup_types_frame.grid(row=2, column=0, sticky="ew", padx=10)
        self._populate_mockup_checkboxes()

        mo = ctk.CTkFrame(mk, fg_color="transparent"); mo.grid(row=3, column=0, sticky="ew", padx=10, pady=3)
        mo.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(mo, text="Orientation:").grid(row=0, column=0, padx=(10, 5))
        self.orientation_var = ctk.StringVar(value="landscape")
        ctk.CTkOptionMenu(mo, variable=self.orientation_var, values=["landscape", "portrait"]).grid(row=0, column=1, sticky="ew")

        self.preserve_ar_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(mk, text="Preserve Aspect Ratio", variable=self.preserve_ar_var).grid(row=4, column=0, sticky="ew", padx=(20, 10), pady=1)
        self.perspective_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(mk, text="Apply Perspective Transform", variable=self.perspective_var).grid(row=5, column=0, sticky="ew", padx=(20, 10), pady=1)
        ctk.CTkButton(mk, text="Generate Mockups", command=self._on_generate_mockups,
                      fg_color="#2FA572", hover_color="#25805A").grid(row=6, column=0, sticky="", padx=10, pady=8)

        # 4. Export
        ex = ctk.CTkFrame(L); ex.grid(row=4, column=0, sticky="ew", padx=10, pady=4)
        ex.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(ex, text="4. Export Print-Ready", font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=0, column=0, sticky="ew", padx=10, pady=(8, 4))
        fr = ctk.CTkFrame(ex, fg_color="transparent"); fr.grid(row=1, column=0, sticky="ew", padx=10, pady=3)
        fr.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(fr, text="Format:").grid(row=0, column=0, padx=(0, 5))
        self.export_format_var = ctk.StringVar(value="PNG")
        ctk.CTkOptionMenu(fr, variable=self.export_format_var, values=["PNG", "JPEG", "TIFF"]).grid(row=0, column=1, sticky="ew")
        qr = ctk.CTkFrame(ex, fg_color="transparent"); qr.grid(row=2, column=0, sticky="ew", padx=10, pady=3)
        qr.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(qr, text="Quality (JPEG):").grid(row=0, column=0, padx=(0, 5))
        self.quality_entry = ctk.CTkEntry(qr, width=80, justify="center")
        self.quality_entry.insert(0, "95")
        self.quality_entry.grid(row=0, column=1, sticky="ew")
        ctk.CTkButton(ex, text="Export All Mockups as Print-Ready", command=self._on_export_print_ready,
                      fg_color="#2FA572", hover_color="#25805A").grid(row=3, column=0, sticky="", padx=10, pady=8)
        # 5. Pinterest Pin
        pn = ctk.CTkFrame(L); pn.grid(row=5, column=0, sticky="ew", padx=10, pady=4)
        pn.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(pn, text="5. Create Pinterest Pin", font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=0, column=0, sticky="ew", padx=10, pady=(8, 4))

        # Pin size
        ps = ctk.CTkFrame(pn, fg_color="transparent"); ps.grid(row=1, column=0, sticky="ew", padx=10, pady=3)
        ps.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(ps, text="Pin Size:").grid(row=0, column=0, padx=(0, 5))
        self.pin_size_var = ctk.StringVar(value="1000x1500 (Standard)")
        ctk.CTkOptionMenu(ps, variable=self.pin_size_var,
                          values=["1000x1500 (Standard)", "1000x2100 (Tall)"]).grid(row=0, column=1, sticky="ew")

        # Background colour
        bc = ctk.CTkFrame(pn, fg_color="transparent"); bc.grid(row=2, column=0, sticky="ew", padx=10, pady=3)
        bc.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(bc, text="Background:").grid(row=0, column=0, padx=(0, 5))
        self.pin_bg_var = ctk.StringVar(value="#ffffff")
        self.pin_bg_entry = ctk.CTkEntry(bc, width=90)
        self.pin_bg_entry.insert(0, "#ffffff")
        self.pin_bg_entry.grid(row=0, column=1, sticky="w")

        # Title
        tt = ctk.CTkFrame(pn, fg_color="transparent"); tt.grid(row=3, column=0, sticky="ew", padx=10, pady=3)
        tt.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(tt, text="Title:").grid(row=0, column=0, padx=(0, 5))
        self.pin_title_entry = ctk.CTkEntry(tt)
        self.pin_title_entry.insert(0, "")
        self.pin_title_entry.grid(row=0, column=1, sticky="ew")

        # Subtitle
        st = ctk.CTkFrame(pn, fg_color="transparent"); st.grid(row=4, column=0, sticky="ew", padx=10, pady=3)
        st.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(st, text="Subtitle/Shop:").grid(row=0, column=0, padx=(0, 5))
        self.pin_sub_entry = ctk.CTkEntry(st)
        self.pin_sub_entry.insert(0, "")
        self.pin_sub_entry.grid(row=0, column=1, sticky="ew")

        # Mockup position
        mp = ctk.CTkFrame(pn, fg_color="transparent"); mp.grid(row=5, column=0, sticky="ew", padx=10, pady=3)
        mp.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(mp, text="Mockup Position:").grid(row=0, column=0, padx=(0, 5))
        self.pin_pos_var = ctk.StringVar(value="top")
        ctk.CTkOptionMenu(mp, variable=self.pin_pos_var,
                          values=["top", "center", "bottom"]).grid(row=0, column=1, sticky="ew")

        # Create button
        ctk.CTkButton(pn, text="Create Pin", command=self._on_create_pin,
                      fg_color="#2FA572", hover_color="#25805A").grid(
            row=6, column=0, sticky="", padx=10, pady=(5, 8))

        # 5. Actions
        ac = ctk.CTkFrame(L, fg_color="transparent"); ac.grid(row=6, column=0, sticky="ew", padx=10, pady=(0, 10))
        ac.grid_columnconfigure(0, weight=1); ac.grid_columnconfigure(1, weight=1)
        ctk.CTkButton(ac, text="Template Manager", command=self._open_template_manager,
                      fg_color="#6A4C93", hover_color="#543B75").grid(row=0, column=0, sticky="ew", padx=(0, 4), pady=4)
        ctk.CTkButton(ac, text="Clear / Reset", command=self._on_clear,
                      fg_color="#BD081C", hover_color="#8F0614").grid(row=0, column=1, sticky="ew", padx=(4, 0), pady=4)
        ctk.CTkButton(ac, text="Batch Process", command=self._open_batch,
                      fg_color="#1F6AA5", hover_color="#184F77").grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 4))

    def _on_create_pin(self):
        if not self.generated_mockup_paths:
            messagebox.showwarning("No Mockups", "Generate at least one mockup first.")
            return

        # Parse pin size
        ps = self.pin_size_var.get()
        if "1500" in ps:
            pw, ph = 1000, 1500
        else:
            pw, ph = 1000, 2100

        bg = self.pin_bg_entry.get().strip()
        if not bg.startswith("#"):
            bg = "#" + bg
        title = self.pin_title_entry.get().strip()
        subtitle = self.pin_sub_entry.get().strip()
        pos = self.pin_pos_var.get()

        self._set_status(f"Creating {len(self.generated_mockup_paths)} pin(s)...")
        self.update()

        count = 0
        for mp in self.generated_mockup_paths:
            result = create_pinterest_pin(
                mockup_path=mp,
                output_dir=PINTEREST_FOLDER,
                pin_width=pw,
                pin_height=ph,
                bg_color=bg,
                title=title,
                subtitle=subtitle,
                mockup_position=pos
            )
            if result:
                count += 1
                self._show_image_preview(result, f"Pin: {os.path.basename(result)}")

        if count:
            self._set_status(f"Created {count} pin(s) in {PINTEREST_FOLDER}/")
            messagebox.showinfo("Done", f"{count} Pinterest pin(s) saved to:\n{os.path.abspath(PINTEREST_FOLDER)}")
        else:
            self._set_status("Pin creation failed. Check console.")
            messagebox.showerror("Error", "Pin creation failed. Check the console output.")
      

    def _populate_mockup_checkboxes(self):
        for w in self.mockup_types_frame.winfo_children():
            w.destroy()
        self.mockup_vars = {}
        for i, m_type in enumerate(mockup_generator.MOCKUP_CONFIGS.keys()):
            var = ctk.BooleanVar(value=(m_type == "living_room"))
            self.mockup_vars[m_type] = var
            ctk.CTkCheckBox(self.mockup_types_frame, text=m_type.replace('_', ' ').title(),
                            variable=var).grid(row=i, column=0, sticky="ew", padx=5, pady=1)

    # ── RIGHT ──────────────────────────────────────────────────────
    def _build_right_panel(self):
        ctk.CTkLabel(self.right_panel, text="Preview", font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0, column=0, pady=(10, 5))
        self.preview_canvas = ctk.CTkScrollableFrame(self.right_panel)
        self.preview_canvas.grid(row=1, column=0, sticky="nsew", padx=5, pady=(0, 5))
        self.preview_canvas.grid_columnconfigure(0, weight=1)
        self._show_placeholder()

    def _show_placeholder(self):
        ctk.CTkLabel(self.preview_canvas,
                     text="Upload an image to begin\n\n1. Select artwork\n2. Upscale\n3. Mockups\n4. Export",
                     font=ctk.CTkFont(size=14), text_color="gray", justify="center").grid(row=0, column=0, pady=50)

    # ── SPEC (two columns: original vs upscaled) ───────────────────
    def _build_spec_panel(self):
        spec = ctk.CTkFrame(self)
        spec.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        spec.grid_columnconfigure(0, weight=1)
        spec.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(spec, text="Original artwork", font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=0, column=0, sticky="ew", padx=(10, 5), pady=(6, 2))
        ctk.CTkLabel(spec, text="Upscaled output", font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=0, column=1, sticky="ew", padx=(5, 10), pady=(6, 2))

        self.spec_original = ctk.CTkTextbox(spec, height=130, font=("Consolas", 10), wrap="none")
        self.spec_original.grid(row=1, column=0, sticky="nsew", padx=(10, 5), pady=(0, 8))
        self.spec_upscaled = ctk.CTkTextbox(spec, height=130, font=("Consolas", 10), wrap="none")
        self.spec_upscaled.grid(row=1, column=1, sticky="nsew", padx=(5, 10), pady=(0, 8))

        self._set_spec(self.spec_original, "(none)")
        self._set_spec(self.spec_upscaled, "(none)")
                # ── RIGHT HALF: Batch summary ──────────────────────────────────
        summary = ctk.CTkFrame(self)
        summary.grid(row=1, column=1, sticky="ew", padx=(5, 10), pady=5)
        summary.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(summary, text="Batch Summary",
                     font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(6, 4))

        self._summary_labels = {}

        rows = [
            ("Artwork folder:",   "folder"),
            ("Images in folder:", "images"),
            ("Sizes selected:",   "sizes"),
            ("Mockups selected:", "mockups"),
            ("Files per image:",  "per_image"),
            ("Total files:",      "total"),
        ]

        for i, (label_text, key) in enumerate(rows, start=1):
            ctk.CTkLabel(summary, text=label_text, anchor="w").grid(
                row=i, column=0, sticky="w", padx=10, pady=2)
            val_label = ctk.CTkLabel(summary, text="0", anchor="e",
                                      font=ctk.CTkFont(size=12, weight="bold")
                                      if key == "total" else None)
            val_label.grid(row=i, column=1, sticky="ew", padx=10, pady=2)
            self._summary_labels[key] = val_label
    def _update_summary(self):
        if not hasattr(self, "_summary_labels"):
            return

        folder = getattr(self.batch_proc, "folder", None) if hasattr(self, "batch_proc") else None

        if folder and os.path.isdir(folder):
            folder_name = os.path.basename(os.path.normpath(folder))
            try:
                img_count = sum(
                    1 for f in os.listdir(folder)
                    if f.lower().endswith((".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp"))
                )
            except OSError:
                img_count = 0
        else:
            folder_name = "none"
            img_count = 0

        bp = getattr(self, "batch_proc", None)
        if bp:
            sizes = sum(1 for v in bp.size_vars.values() if v.get())
            mockups = sum(1 for v in bp.mockup_vars.values() if v.get())
        else:
            sizes = 0
            mockups = 0

        per_image = sizes * (1 + mockups) + (1 if sizes else 0)
        total = img_count * per_image

        values = {
            "folder": folder_name,
            "images": img_count,
            "sizes": sizes,
            "mockups": mockups,
            "per_image": per_image,
            "total": total,
        }
        for key, value in values.items():
            if key in self._summary_labels:
                self._summary_labels[key].configure(text=str(value))


    def _set_spec(self, box, text):
        """Robustly set a CTkTextbox's contents (avoids the read-only repaint bug)."""
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("1.0", text)
        box.see("1.0")
        box.configure(state="disabled")
        box.update_idletasks()

    def _refresh_spec_check(self):
        self._set_spec(self.spec_original, build_spec_check_text(self.original_image_path))
        self._set_spec(self.spec_upscaled, build_spec_check_text(self.upscaled_image_path))

    def _build_status_bar(self):
        self.status_var = ctk.StringVar(value="Ready.")
        ctk.CTkLabel(self, textvariable=self.status_var, anchor="w", font=ctk.CTkFont(size=12),
                     fg_color="#2b2b2b", text_color="#aaaaaa").grid(
            row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 5))

    # ── Handlers ───────────────────────────────────────────────────
    def _on_upload(self):
        fp = filedialog.askopenfilename(title="Select Artwork Image",
                                        filetypes=[("Image Files", "*.png *.jpg *.jpeg *.gif *.bmp *.tiff"), ("All Files", "*.*")])
        if not fp:
            return
        if not is_image_file(fp):
            messagebox.showerror("Invalid File", f"'{os.path.basename(fp)}' is not a valid image file."); return
        fn = os.path.basename(fp)
        dest = os.path.join(UPLOAD_FOLDER, fn)
        try:
            with open(fp, 'rb') as s, open(dest, 'wb') as d:
                d.write(s.read())
        except Exception as e:
            messagebox.showerror("Error", f"Could not save file: {e}"); return
        self.original_image_path = dest
        self.upscaled_image_path = None
        self.generated_mockup_paths = []
        self.upload_status_label.configure(text=f"✓ {fn}", text_color="#2FA572")
        self._set_status(f"Uploaded: {fn}")
        self._show_image_preview(dest, "Original")
        self._refresh_spec_check()
        self._update_summary()

    def _open_batch(self):
        self.batch_proc = BatchProcessor(self, on_complete_callback=None)
        self._update_summary()


    def _on_upscale(self):
        if not self.original_image_path:
            messagebox.showwarning("No Image", "Please upload an image first."); return
        ts = self.size_var.get(); to = self.upscale_orient_var.get(); rs = self.resample_var.get()
        fit = "fill_crop" if "Fill" in self.fit_var.get() else "stretch"
        crop_pos = self.crop_pos_var.get().lower()
        self._set_status(f"Upscaling to {ts} ({to}) [{fit}/{crop_pos}]..."); self.update()
        rp = upscale_image(image_path=self.original_image_path, target_size_name=ts,
                           dpi=DEFAULT_DPI, output_dir=UPSCALED_FOLDER,
                           orientation=to, resample=rs, fit=fit, crop_pos=crop_pos)
        if rp:
            self.upscaled_image_path = rp
            self.generated_mockup_paths = []
            self._set_status(f"Upscaled to {ts} ({to}) successfully.")
            self._show_image_preview(rp, f"Upscaled ({ts} {to})")
            self._refresh_spec_check()
        else:
            self._set_status("Upscaling failed. Check console.")
            messagebox.showerror("Upscale Failed", "Upscaling failed. Check the console output.")


    def _on_generate_mockups(self):
        if not self.upscaled_image_path:
            messagebox.showwarning("No Upscaled Image", "Please upscale an image first."); return
        sel = [m for m, v in self.mockup_vars.items() if v.get()]
        if not sel:
            messagebox.showwarning("No Mockups Selected", "Select at least one mockup type."); return
        o = self.orientation_var.get(); pa = self.preserve_ar_var.get(); pp = self.perspective_var.get()
        self.generated_mockup_paths = []
        ok = fail = 0
        for m in sel:
            self._set_status(f"Generating mockup: {m.replace('_', ' ').title()}..."); self.update()
            r = generate_mockup(artwork_path=self.upscaled_image_path, mockup_type=m,
                                artwork_orientation=o, output_dir=MOCKUP_FOLDER,
                                preserve_aspect_ratio=pa, apply_perspective=pp)
            if r:
                self.generated_mockup_paths.append(r); ok += 1
                self._show_image_preview(r, f"Mockup: {m.replace('_', ' ').title()}")
            else:
                fail += 1
        if ok:
            self._set_status(f"Generated {ok} mockup(s)." + (f" {fail} failed." if fail else ""))
        else:
            self._set_status("Mockup generation failed. Check template paths in mockup_configs.json.")
            messagebox.showerror("Mockup Failed", "No mockups generated. Check template image paths in mockup_configs.json.")

    def _on_export_print_ready(self):
        if not self.generated_mockup_paths:
            messagebox.showwarning("No Mockups", "Generate at least one mockup first."); return
        fmt = self.export_format_var.get()
        try:
            q = int(self.quality_entry.get())
        except ValueError:
            q = 95
        q = max(1, min(100, q))
        self._set_status(f"Exporting {len(self.generated_mockup_paths)} file(s) as {fmt}..."); self.update()
        n = 0
        for mp in self.generated_mockup_paths:
            if export_print_ready_image(mockup_image_path=mp, output_dir=PRINT_READY_FOLDER, format=fmt, quality=q):
                n += 1
        if n:
            self._set_status(f"Exported {n} print-ready file(s) to {PRINT_READY_FOLDER}/")
            messagebox.showinfo("Export Complete", f"{n} file(s) saved to:\n{os.path.abspath(PRINT_READY_FOLDER)}")
       
        else:
            self._set_status("Print-ready export failed. Check console.")
            messagebox.showerror("Export Failed", "Export failed. Check the console output.")

    def _open_template_manager(self):
        TemplateManager(self, on_apply_callback=self._on_templates_changed)

    def _on_templates_changed(self):
        load_mockup_configs()
        self._populate_mockup_checkboxes()
        self._set_status("Template configs updated.")

    def _on_clear(self):
        self.original_image_path = None
        self.upscaled_image_path = None
        self.generated_mockup_paths = []
        self.preview_images = []
        self.upload_status_label.configure(text="No file selected", text_color="gray")
        for w in self.preview_canvas.winfo_children():
            w.destroy()
        self._show_placeholder()
        self._refresh_spec_check()
        self._set_status("Cleared. Ready.")

    def _set_status(self, text):
        self.status_var.set(text)

    def _show_image_preview(self, path, label):
        for w in self.preview_canvas.winfo_children():
            if isinstance(w, ctk.CTkLabel) and not getattr(w, "image", None):
                if "Upload an image" in str(w.cget("text")):
                    w.destroy(); break
        try:
            im = Image.open(path); im.thumbnail((420, 420), Image.LANCZOS)
            cimg = ctk.CTkImage(light_image=im, dark_image=im, size=im.size)
            self.preview_images.append(cimg)
            row = len(self.preview_canvas.winfo_children())
            ctk.CTkLabel(self.preview_canvas, text=f"─── {label} ───",
                         font=ctk.CTkFont(size=12, weight="bold"), text_color="#aaaaaa").grid(row=row*2, column=0, pady=(15, 2))
            ctk.CTkLabel(self.preview_canvas, image=cimg, text="").grid(row=row*2+1, column=0, pady=(0, 5))
        except Exception as e:
            self._set_status(f"Error displaying image: {e}")


def main():
    app = EtsyPrintShopApp()
    app.mainloop()
    print("Script finished execution (this should only happen AFTER app.mainloop() exits).")


if __name__ == "__main__":
    main()
