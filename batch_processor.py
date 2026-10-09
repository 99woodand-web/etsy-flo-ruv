# batch_processor.py
# Batch processor: point at a folder of artwork, run the full pipeline
# (upscale all selected sizes, mockups per size, print-ready export, pin)
# and collect everything into one tidy folder per artwork.

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image

import mockup_generator
from image_uploader_manager import is_image_file
from upscaling_resolution_tool import PRINT_SIZES_MM, upscale_image
from mockup_generator import generate_mockup
from print_ready_exporter import export_print_ready_image
from pinterest_pin_maker import create_pinterest_pin
from listing_bundle import create_listing_bundle

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff'}
DEFAULT_DPI = 300


class BatchProcessor(tk.Toplevel):
    def __init__(self, master, on_complete_callback=None):
        super().__init__(master)
        self.master = master
        self.on_complete_callback = on_complete_callback

        self.title("Batch Processor")
        self.geometry("880x820")
        self.minsize(820, 700)
        self.resizable(True, True)

        self.configure(bg="#2b2b2b")

        self.folder = ""
        self.size_vars = {s: tk.BooleanVar(value=True) for s in PRINT_SIZES_MM}
        self.running = False

        self._build_ui()
        self.grab_set()

    def _build_ui(self):
        pad = {"padx": 12, "pady": 4}

        # Folder picker
        row0 = tk.Frame(self, bg="#2b2b2b"); row0.pack(fill="x", **pad)
        tk.Label(row0, text="Artwork Folder:", bg="#2b2b2b", fg="white").pack(side="left")
        from pathlib import Path
        self.folder_entry = tk.Entry(row0, width=35, bg="#4a4a4a", fg="white", insertbackground="white")
        import os
        _script_dir = os.path.dirname(os.path.abspath(__file__))
        _default_artwork = os.path.join(_script_dir, "Pictures")
        self.folder_entry.insert(0, _default_artwork)
        self.folder = _default_artwork

        tk.Button(row0, text="Browse", command=self._browse_folder, bg="#4a4a4a",
                  fg="white", relief="flat", padx=8).pack(side="left")

        # Sizes
        row1 = tk.Frame(self, bg="#2b2b2b"); row1.pack(fill="x", **pad)
        tk.Label(row1, text="Print Sizes:", bg="#2b2b2b", fg="white").pack(side="left", padx=(0, 8))
        for size in PRINT_SIZES_MM:
            tk.Checkbutton(row1, text=size, variable=self.size_vars[size],
                           bg="#2b2b2b", fg="white", selectcolor="#4a4a4a").pack(side="left", padx=4)
        tk.Button(row1, text="All", command=self._select_all_sizes, bg="#4a4a4a",
                  fg="white", relief="flat", padx=8).pack(side="left", padx=8)
        tk.Button(row1, text="None", command=self._deselect_all_sizes, bg="#4a4a4a",
                  fg="white", relief="flat", padx=8).pack(side="left")

        # Upscale options
        row2 = tk.Frame(self, bg="#2b2b2b"); row2.pack(fill="x", **pad)
        tk.Label(row2, text="Upscale:", bg="#2b2b2b", fg="white").pack(side="left", padx=(0, 8))
        self.orient_var = tk.StringVar(value="auto")
        for val in ("auto", "portrait", "landscape"):
            tk.Radiobutton(row2, text=val, variable=self.orient_var, value=val,
                           bg="#2b2b2b", fg="white", selectcolor="#4a4a4a").pack(side="left", padx=3)

        row3 = tk.Frame(self, bg="#2b2b2b"); row3.pack(fill="x", **pad)
        tk.Label(row3, text="Quality:", bg="#2b2b2b", fg="white").pack(side="left", padx=(0, 8))
        self.quality_var = tk.StringVar(value="realesrgan")
        for val in ("bicubic", "lanczos", "realesrgan"):
            label = "ESRGAN (AI)" if val == "realesrgan" else val
            tk.Radiobutton(row3, text=label, variable=self.quality_var, value=val,
                        bg="#2b2b2b", fg="white", selectcolor="#4a4a4a").pack(side="left", padx=3)

        tk.Label(row3, text="   Fit:", bg="#2b2b2b", fg="white").pack(side="left", padx=(15, 4))

        self.fit_var = tk.StringVar(value="fill_crop")
        for val in ("fill_crop", "stretch"):
            label = "Fill & Crop" if val == "fill_crop" else "Stretch"
            tk.Radiobutton(row3, text=label, variable=self.fit_var, value=val,
                           bg="#2b2b2b", fg="white", selectcolor="#4a4a4a").pack(side="left", padx=3)
        tk.Label(row3, text="   Crop:", bg="#2b2b2b", fg="white").pack(side="left", padx=(15, 4))
        self.crop_var = tk.StringVar(value="center")
        for val in ("center", "top", "bottom", "left", "right"):
            tk.Radiobutton(row3, text=val, variable=self.crop_var, value=val,
                           bg="#2b2b2b", fg="white", selectcolor="#4a4a4a").pack(side="left", padx=2)

        # Mockup options
        row4 = tk.Frame(self, bg="#2b2b2b"); row4.pack(fill="x", **pad)
        tk.Label(row4, text="Mockups:", bg="#2b2b2b", fg="white").pack(side="left", padx=(0, 8))
        self.mockup_vars = {}
        for m_type in mockup_generator.MOCKUP_CONFIGS.keys():
            var = tk.BooleanVar(value=True)
            self.mockup_vars[m_type] = var
            tk.Checkbutton(row4, text=m_type.replace('_', ' ').title(), variable=var,
                           bg="#2b2b2b", fg="white", selectcolor="#4a4a4a",
                           command=lambda: self.master._update_summary()).pack(side="left", padx=4)


        row5 = tk.Frame(self, bg="#2b2b2b"); row5.pack(fill="x", **pad)
        tk.Label(row5, text="Orientation:", bg="#2b2b2b", fg="white").pack(side="left", padx=(0, 8))
        self.m_orient_var = tk.StringVar(value="landscape")
        for val in ("landscape", "portrait"):
            tk.Radiobutton(row5, text=val, variable=self.m_orient_var, value=val,
                           bg="#2b2b2b", fg="white", selectcolor="#4a4a4a").pack(side="left", padx=3)
        self.ar_var = tk.BooleanVar(value=True)
        tk.Checkbutton(row5, text="Aspect Ratio", variable=self.ar_var,
                       bg="#2b2b2b", fg="white", selectcolor="#4a4a4a").pack(side="left", padx=8)
        self.persp_var = tk.BooleanVar(value=False)
        tk.Checkbutton(row5, text="Perspective", variable=self.persp_var,
                       bg="#2b2b2b", fg="white", selectcolor="#4a4a4a").pack(side="left")

        # Pin options
        row6 = tk.Frame(self, bg="#2b2b2b"); row6.pack(fill="x", **pad)
        tk.Label(row6, text="Pin Size:", bg="#2b2b2b", fg="white").pack(side="left", padx=(0, 8))
        self.pin_size_var = tk.StringVar(value="1000x1500")
        tk.Radiobutton(row6, text="Standard", variable=self.pin_size_var, value="1000x1500",
                       bg="#2b2b2b", fg="white", selectcolor="#4a4a4a").pack(side="left", padx=3)
        tk.Radiobutton(row6, text="Tall", variable=self.pin_size_var, value="1000x2100",
                       bg="#2b2b2b", fg="white", selectcolor="#4a4a4a").pack(side="left", padx=3)

        tk.Label(row6, text="Title:", bg="#2b2b2b", fg="white").pack(side="left", padx=(15, 4))
        self.pin_title_entry = tk.Entry(row6, width=20, bg="#4a4a4a", fg="white", insertbackground="white")
        self.pin_title_entry.pack(side="left", padx=4)
        tk.Label(row6, text="Subtitle:", bg="#2b2b2b", fg="white").pack(side="left", padx=(8, 4))
        self.pin_sub_entry = tk.Entry(row6, width=20, bg="#4a4a4a", fg="white", insertbackground="white")
        self.pin_sub_entry.pack(side="left", padx=4)

        # Output folder
        row7 = tk.Frame(self, bg="#2b2b2b"); row7.pack(fill="x", **pad)
        tk.Label(row7, text="Output To:", bg="#2b2b2b", fg="white").pack(side="left")
        self.output_entry = tk.Entry(row7, width=35, bg="#4a4a4a", fg="white", insertbackground="white")
        self.output_entry.insert(0, "Batch output")
        self.output_entry.pack(side="left", padx=5)
        tk.Button(row7, text="Browse", command=self._browse_output, bg="#4a4a4a",
                  fg="white", relief="flat", padx=8).pack(side="left")

        # Progress
        self.progress = ttk.Progressbar(self, length=600, mode="determinate")
        self.progress.pack(fill="x", padx=12, pady=6)
        self.status_label = tk.Label(self, text="Ready.", bg="#2b2b2b", fg="#8fd", anchor="w")
        self.status_label.pack(fill="x", padx=12, pady=2)

        # Run button
        tk.Button(self, text="Run Batch", command=self._run_batch,
                  bg="#2FA572", fg="white", relief="flat", padx=30, pady=8,
                  font=("Arial", 12, "bold")).pack(pady=10)

    def _browse_folder(self):
        d = filedialog.askdirectory(title="Select Artwork Folder", parent=self)
        if d:
            self.folder = d
            self.folder_entry.delete(0, "end")
            self.folder_entry.insert(0, d)
        self.master._update_summary()

    def _browse_output(self):
        d = filedialog.askdirectory(title="Select Output Folder", parent=self)
        if d:
            self.output_entry.delete(0, "end")
            self.output_entry.insert(0, d)

    def _select_all_sizes(self):
        for v in self.size_vars.values():
            v.set(True)

    def _deselect_all_sizes(self):
        for v in self.size_vars.values():
            v.set(False)

    def _get_images(self):
        """List all valid image files in the selected folder (non-recursive)."""
        if not self.folder or not os.path.isdir(self.folder):
            return []
        files = []
        for f in sorted(os.listdir(self.folder)):
            ext = os.path.splitext(f)[1].lower().lstrip('.')
            if ext in ALLOWED_EXTENSIONS and os.path.isfile(os.path.join(self.folder, f)):
                full = os.path.join(self.folder, f)
                if is_image_file(full):
                    files.append(full)
        return files

    def _set_status(self, text):
        self.status_label.configure(text=text)
        self.update()

    def _run_batch(self):
        if self.running:
            return
        if not self.folder or not os.path.isdir(self.folder):
            messagebox.showwarning("No Folder", "Select an artwork folder first.", parent=self)
            return
        if not any(v.get() for v in self.size_vars.values()):
            messagebox.showwarning("No Sizes", "Select at least one print size.", parent=self)
            return
        if not any(v.get() for v in self.mockup_vars.values()):
            messagebox.showwarning("No Mockups", "Select at least one mockup type.", parent=self)
            return

        images = self._get_images()
        if not images:
            messagebox.showwarning("No Images", "No valid image files found in that folder.", parent=self)
            return

        self.running = True
        self.progress.configure(maximum=1, value=0)

        selected_sizes = [s for s in PRINT_SIZES_MM if self.size_vars[s].get()]
        selected_mockups = [m for m in self.mockup_vars if self.mockup_vars[m].get()]
        output_root = self.output_entry.get().strip() or "batch_output"

        orient = self.orient_var.get()
        quality = self.quality_var.get()
        fit = self.fit_var.get()
        crop_pos = self.crop_var.get()
        m_orient = self.m_orient_var.get()
        ar = self.ar_var.get()
        persp = self.persp_var.get()

        pin_size = self.pin_size_var.get()
        pw, ph = (1000, 1500) if "1500" in pin_size else (1000, 2100)
        pin_title = self.pin_title_entry.get().strip()
        pin_sub = self.pin_sub_entry.get().strip()

        total_images = len(images)
        total_steps = total_images * (len(selected_sizes) * (1 + len(selected_mockups) * 2) + 1)
        self.progress.configure(maximum=total_steps)
        step = 0

        success_count = 0
        fail_count = 0

        for img_idx, img_path in enumerate(images):
            img_name = os.path.splitext(os.path.basename(img_path))[0]
            art_folder = os.path.join(output_root, img_name)
            first_mockup = None

            self._set_status(f"[{img_idx+1}/{total_images}] {img_name} — processing {len(selected_sizes)} size(s)...")

            for size in selected_sizes:
                size_folder = os.path.join(art_folder, size)
                os.makedirs(size_folder, exist_ok=True)

                # Upscale
                upscaled = upscale_image(
                    image_path=img_path,
                    target_size_name=size,
                    dpi=DEFAULT_DPI,
                    output_dir=size_folder,
                    orientation=orient,
                    resample=quality,
                    fit=fit,
                    crop_pos=crop_pos
                )
                step += 1
                self.progress.configure(value=step)

                if not upscaled:
                    self._set_status(f"  [{img_name}/{size}] Upscale FAILED")
                    fail_count += 1
                    continue

                # Mockups
                for m_type in selected_mockups:
                    mockup = generate_mockup(
                        artwork_path=upscaled,
                        mockup_type=m_type,
                        artwork_orientation=m_orient,
                        output_dir=size_folder,
                        preserve_aspect_ratio=ar,
                        apply_perspective=persp
                    )
                    step += 1
                    self.progress.configure(value=step)
                    if not mockup:
                        continue
                    if first_mockup is None:
                        first_mockup = mockup

                    # Print-ready export
                    #export_print_ready_image(
                     #   mockup_image_path=mockup,
                      #  output_dir=size_folder,
                       # format="PNG"
                  #  )
                    step += 1
                    self.progress.configure(value=step)

            # Pin (one per artwork, from the first successful mockup)
            if first_mockup:
                pin_folder = os.path.join(art_folder, "pin")
                os.makedirs(pin_folder, exist_ok=True)
                create_pinterest_pin(
                    mockup_path=first_mockup,
                    output_dir=pin_folder,
                    pin_width=pw,
                    pin_height=ph,
                    title=pin_title,
                    subtitle=pin_sub
                )
            step += 1
            self.progress.configure(value=step)

            success_count += 1

        self.running = False
        self._set_status(f"Done. {success_count} artwork(s) processed, {fail_count} error(s).")
        messagebox.showinfo("Batch Complete",
                            f"{success_count} artwork(s) processed.\n"
                            f"Output: {os.path.abspath(output_root)}",
                            parent=self)
        if self.on_complete_callback:
            self.on_complete_callback()
         

