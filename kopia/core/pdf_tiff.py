from pathlib import Path
import tempfile
import pymupdf as fitz
from PIL import Image

def validate_pdf(path: Path):
    if not path.is_file() or path.stat().st_size < 100: raise RuntimeError(f"PDF non valido: {path}")
    with path.open("rb") as f:
        if f.read(5) != b"%PDF-": raise RuntimeError(f"Header PDF non valido: {path}")
    with fitz.open(path) as doc:
        if doc.page_count < 1: raise RuntimeError("PDF senza pagine.")

def validate_tiff(path: Path):
    if not path.is_file() or path.stat().st_size <= 0: raise RuntimeError(f"TIFF non valido: {path}")
    with Image.open(path) as im:
        if im.format != "TIFF": raise RuntimeError(f"Formato inatteso: {im.format}")
        for i in range(getattr(im, "n_frames", 1)): im.seek(i); im.load()

def is_color_300dpi_tiff(path: Path):
    try:
        with Image.open(path) as im:
            dpi = im.info.get("dpi", (0, 0))
            return im.mode == "RGB" and abs(float(dpi[0])-300) < 1 and abs(float(dpi[1])-300) < 1
    except (OSError, TypeError, ValueError, IndexError): return False

def is_ccitt_600dpi_tiff(path: Path):
    try:
        with Image.open(path) as im:
            dpi = im.info.get("dpi", (0, 0)); compression = str(im.info.get("compression", "")).lower()
            return im.mode == "1" and "group4" in compression and abs(float(dpi[0])-600) < 1 and abs(float(dpi[1])-600) < 1
    except (OSError, TypeError, ValueError, IndexError): return False

def _render_pdf_pages(pdf_path: Path, dpi: int, colorspace):
    validate_pdf(pdf_path); pages = []
    with fitz.open(pdf_path) as doc:
        matrix = fitz.Matrix(dpi/72, dpi/72)
        for page in doc:
            pix = page.get_pixmap(matrix=matrix, colorspace=colorspace, alpha=False)
            mode = "RGB" if colorspace == fitz.csRGB else "L"
            pages.append(Image.frombytes(mode, (pix.width, pix.height), pix.samples).copy())
    if not pages: raise RuntimeError("PDF senza pagine.")
    return pages

def convert_pdf_to_tiff_300dpi_color(pdf_path: Path, tiff_path: Path):
    tmp = tiff_path.with_name(f".{tiff_path.stem}.tmp.tiff"); tmp.unlink(missing_ok=True); pages = []
    try:
        pages = _render_pdf_pages(pdf_path, 300, fitz.csRGB)
        pages[0].save(tmp, format="TIFF", save_all=True, append_images=pages[1:], compression="tiff_lzw", dpi=(300, 300))
        validate_tiff(tmp); tmp.replace(tiff_path); validate_tiff(tiff_path)
    except Exception: tmp.unlink(missing_ok=True); raise
    finally:
        for im in pages:
            try: im.close()
            except: pass

def convert_pdf_to_tiff_600dpi(pdf_path: Path, tiff_path: Path):
    validate_pdf(pdf_path); tmp = tiff_path.with_name(f".{tiff_path.stem}.tmp.tiff"); tmp.unlink(missing_ok=True); pages = []
    try:
        with fitz.open(pdf_path) as doc:
            for page in doc:
                pix = page.get_pixmap(matrix=fitz.Matrix(600/72, 600/72), colorspace=fitz.csGRAY, alpha=False)
                gray = Image.frombytes("L", (pix.width, pix.height), pix.samples)
                bw = gray.point(lambda value: 0 if value < 200 else 255, mode="1")
                pages.append(bw.copy()); bw.close(); gray.close()
        if not pages: raise RuntimeError("PDF senza pagine.")
        pages[0].save(tmp, format="TIFF", save_all=True, append_images=pages[1:], compression="group4", dpi=(600, 600))
        validate_tiff(tmp); tmp.replace(tiff_path); validate_tiff(tiff_path)
    except Exception: tmp.unlink(missing_ok=True); raise
    finally:
        for im in pages:
            try: im.close()
            except: pass

def _pdf_with_jpeg_pages(pages, output, dpi=300):
    doc = fitz.open()
    for stream, width, height in pages:
        page = doc.new_page(width=width*72/dpi, height=height*72/dpi)
        page.insert_image(page.rect, stream=stream)
    doc.save(output, garbage=4, deflate=True)
    doc.close()

def compress_pdf_300dpi(src: Path, dst: Path):
    """Create a portable, compressed 300 DPI PDF without external encoders."""
    validate_pdf(src); tmp = dst.with_name(f".{dst.stem}.tmp.pdf"); tmp.unlink(missing_ok=True); pages = []
    try:
        with tempfile.TemporaryDirectory(prefix="color-pdf-") as work:
            for index, image in enumerate(_render_pdf_pages(src, 300, fitz.csRGB)):
                jpg = Path(work) / f"page-{index:04d}.jpg"
                image.save(jpg, format="JPEG", quality=72, optimize=True, subsampling=0, dpi=(300, 300))
                pages.append((jpg.read_bytes(), image.width, image.height)); image.close()
        _pdf_with_jpeg_pages(pages, tmp, 300); validate_pdf(tmp); tmp.replace(dst); validate_pdf(dst)
    except Exception: tmp.unlink(missing_ok=True); raise

compress_pdf = compress_pdf_300dpi
