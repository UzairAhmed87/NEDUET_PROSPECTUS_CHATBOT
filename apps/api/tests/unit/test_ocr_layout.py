from app.services.ocr_layout import (
    OcrLine,
    find_gutter,
    fix_digit_confusions,
    layout_page,
    order_lines,
    repeated_margin_keys,
    section_heading,
)

WIDTH = 1000.0
HEIGHT = 1400.0


def _line(text: str, x0: float, y0: float, x1: float, height: float = 20.0, score: float = 0.95) -> OcrLine:
    return OcrLine(text, x0, y0, x1, y0 + height, score)


def _two_column_fee_page() -> list[OcrLine]:
    # Engine order deliberately interleaves the columns, as RapidOCR does on the prospectus.
    return [
        _line("8.1 FEE AND CHARGES", 60, 200, 400),
        _line("8.2 CHARGES UNDER SELF-FINANCE SCHEME", 540, 200, 940),
        _line("All BE, BS & B. Arch except BS (CT)", 60, 240, 330),
        _line("Rs. 51,930/-", 360, 240, 460),
        _line("Categories SF-1 to SF-5", 540, 240, 760),
        _line("Rs. 855,000/-", 800, 240, 930),
        _line("BS (CT) Programmes", 60, 280, 260),
        _line("Rs. 56,390/-", 360, 280, 460),
        _line("Categories SF-6 to SF-11", 540, 280, 760),
        _line("Rs.1,065,000/-", 800, 280, 940),
    ]


def test_gutter_found_between_columns() -> None:
    gutter = find_gutter(_two_column_fee_page(), WIDTH)
    assert gutter is not None
    assert 460 < gutter < 540


def test_columns_read_top_to_bottom_and_rows_keep_amounts() -> None:
    text, columns = order_lines(_two_column_fee_page(), WIDTH)
    assert columns == 2
    lines = [line for line in text.split("\n") if line.strip()]
    assert "BS (CT) Programmes Rs. 56,390/-" in lines
    assert "Categories SF-6 to SF-11 Rs.1,065,000/-" in lines
    assert text.index("56,390") < text.index("8.2 CHARGES")
    assert text.index("51,930") < text.index("855,000")


def test_single_column_page_is_left_in_row_order() -> None:
    lines = [_line("First paragraph line", 60, 200, 900), _line("Second line", 60, 230, 900)]
    text, columns = order_lines(lines, WIDTH)
    assert columns == 1
    assert text.index("First") < text.index("Second")


def test_spanning_line_separates_column_segments() -> None:
    lines = [
        _line("left top", 60, 200, 400),
        _line("right top", 560, 200, 900),
        _line("left a", 60, 230, 400),
        _line("right a", 560, 230, 900),
        _line("left b", 60, 260, 400),
        _line("right b", 560, 260, 900),
        _line("FULL WIDTH TITLE ACROSS THE PAGE", 60, 400, 940),
        _line("left bottom", 60, 450, 400),
        _line("right bottom", 560, 450, 900),
    ]
    text, _ = order_lines(lines, WIDTH)
    assert text.index("right b") < text.index("FULL WIDTH") < text.index("left bottom")


def test_repeated_footer_removed_with_ocr_noise_and_printed_page_kept() -> None:
    pages = []
    for index, footer in enumerate(["OfONEDUETOfficial", "OONEDUETOfficial", "fONEDUETOfficial", "OOONEDUETOfficial"]):
        pages.append(
            [
                _line("www.neduet.edu.pk", 60, 1340, 300),
                _line(footer, 600, 1340, 900),
                _line(str(90 + index), 480, 1340, 520),
                _line(f"Unique body text {index}", 60, 400, 900),
            ]
        )
    repeated = repeated_margin_keys([(lines, HEIGHT) for lines in pages])
    layout = layout_page(pages[1], WIDTH, HEIGHT, repeated)
    assert "NEDUET" not in layout.text
    assert "neduet.edu.pk" not in layout.text
    assert "Unique body text 1" in layout.text
    assert layout.printed_page == "91"


def test_unique_margin_text_is_kept() -> None:
    lines = [_line("8.1 FEE AND CHARGES", 60, 100, 400), _line("Body", 60, 400, 400)]
    layout = layout_page(lines, WIDTH, HEIGHT, repeated_margins=set())
    assert "8.1 FEE AND CHARGES" in layout.text


def test_digit_fix_is_conservative_and_reported() -> None:
    text, changes = fix_digit_confusions("Fee Rs.5,00o/- and 12,ooo students; 1oth day; go to room o2; No. 7")
    assert "Rs.5,000/-" in text
    assert "12,000 students" in text
    assert "1oth day" in text
    assert "go to" in text
    assert "room o2" in text
    assert ("5,00o", "5,000") in changes
    assert len(changes) == 2


def test_section_heading_detection() -> None:
    assert section_heading("8.1 FEE AND CHARGES (NON-REFUNDABLE)") == ("8.1", "FEE AND CHARGES (NON-REFUNDABLE)")
    assert section_heading("8.3SECURITYDEPOSIT") == ("8.3", "SECURITYDEPOSIT")
    assert section_heading("8.1.2.For Thar Institute of Engineering, Sciences and")[0] == "8.1.2"
    assert section_heading("4.2.1 Applicant should be domiciled in Sindh Province, except") is None
    assert section_heading("Rs. 51,930/-") is None
