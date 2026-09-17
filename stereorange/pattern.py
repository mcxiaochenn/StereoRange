"""生成具有精确物理尺寸的双目标定棋盘格。"""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


def generate_checkerboard_files(
    output_dir: Path,
    board_size: tuple[int, int] = (9, 6),
    square_size_mm: float = 25.0,
) -> tuple[Path, Path]:
    """生成 A4 横向 PDF 与 SVG；board_size 表示内角点数量。"""

    columns, rows = _validate_pattern(board_size, square_size_mm)
    output_dir.mkdir(parents=True, exist_ok=True)
    size_label = f"{square_size_mm:g}mm"
    stem = f"stereorange_checkerboard_{board_size[0]}x{board_size[1]}_{size_label}_a4"
    pdf_path = output_dir / f"{stem}.pdf"
    svg_path = output_dir / f"{stem}.svg"

    board_width = columns * square_size_mm
    board_height = rows * square_size_mm
    origin_x = (297.0 - board_width) / 2.0
    origin_y = (210.0 - board_height) / 2.0

    pdf = canvas.Canvas(str(pdf_path), pagesize=landscape(A4))
    pdf.setTitle("StereoRange 9x6 Checkerboard - 25 mm")
    pdf.setFillColorRGB(1, 1, 1)
    pdf.rect(0, 0, 297 * mm, 210 * mm, fill=1, stroke=0)
    pdf.setFillColorRGB(0, 0, 0)
    for row in range(rows):
        for column in range(columns):
            if (row + column) % 2 == 0:
                pdf.rect(
                    (origin_x + column * square_size_mm) * mm,
                    (origin_y + (rows - row - 1) * square_size_mm) * mm,
                    square_size_mm * mm,
                    square_size_mm * mm,
                    fill=1,
                    stroke=0,
                )
    pdf.showPage()
    pdf.save()

    squares = []
    for row in range(rows):
        for column in range(columns):
            if (row + column) % 2 == 0:
                x = origin_x + column * square_size_mm
                y = origin_y + row * square_size_mm
                squares.append(
                    f'  <rect x="{x:g}mm" y="{y:g}mm" '
                    f'width="{square_size_mm:g}mm" height="{square_size_mm:g}mm" fill="black" />'
                )
    description = escape(
        f"{board_size[0]}x{board_size[1]} inner corners, {square_size_mm:g} mm squares"
    )
    svg = "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<svg xmlns="http://www.w3.org/2000/svg" width="297mm" height="210mm">',
            f"  <title>{description}</title>",
            '  <rect x="0" y="0" width="297mm" height="210mm" fill="white" />',
            *squares,
            "</svg>",
            "",
        ]
    )
    svg_path.write_text(svg, encoding="utf-8")
    return pdf_path, svg_path


def _validate_pattern(
    board_size: tuple[int, int], square_size_mm: float
) -> tuple[int, int]:
    inner_columns, inner_rows = board_size
    if inner_columns < 2 or inner_rows < 2:
        raise ValueError("棋盘格内角点的行列数必须至少为 2。")
    if square_size_mm <= 0:
        raise ValueError("方格边长必须为正数。")
    columns, rows = inner_columns + 1, inner_rows + 1
    if columns * square_size_mm > 297 or rows * square_size_mm > 210:
        raise ValueError("棋盘格尺寸超过 A4 横向页面。")
    return columns, rows
