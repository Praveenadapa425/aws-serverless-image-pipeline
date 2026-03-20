import io

from PIL import Image

from src.image_processor.app import is_supported_image, process_image


def _make_png(width: int = 800, height: int = 400, color=(0, 128, 255)) -> bytes:
    image = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def test_is_supported_image_accepts_jpeg_and_png():
    assert is_supported_image("photo.jpg")
    assert is_supported_image("photo.jpeg")
    assert is_supported_image("image.png")
    assert not is_supported_image("doc.pdf")


def test_process_image_resizes_maintaining_aspect_ratio():
    source = _make_png(width=800, height=400)
    output, original_size, new_size, image_format = process_image(source, 200, "watermark")

    assert image_format == "PNG"
    assert original_size == {"width": 800, "height": 400}
    assert new_size == {"width": 200, "height": 100}

    out_image = Image.open(io.BytesIO(output))
    assert out_image.width == 200
    assert out_image.height == 100
