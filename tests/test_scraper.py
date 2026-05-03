from scraper.download import extract_pdf_links


SAMPLE_HTML = """
<td class="fileDown">
    <a href="/common/BbsFileDown.do?atchFileId=FILE_000000000032340&FileNm=NHF+Daily+Metal+Bulletin+20260501.pdf"
       class="iconSty file" title="NHF Daily Metal Bulletin 20260501.pdf 첨부파일 다운로드">첨부파일</a>
    <a href="/common/BbsFileDown.do?atchFileId=FILE_000000000032340&FileNm=LME+Valuation+20260501.pdf"
       class="iconSty file" title="LME Valuation 20260501.pdf 첨부파일 다운로드">첨부파일</a>
</td>
<td class="fileDown">
    <a href="/common/BbsFileDown.do?atchFileId=FILE_000000000032338&FileNm=NHF+Daily+Metal+Bulletin+20260430.pdf"
       class="iconSty file" title="NHF Daily Metal Bulletin 20260430.pdf 첨부파일 다운로드">첨부파일</a>
    <a href="/common/BbsFileDown.do?atchFileId=FILE_000000000032338&FileNm=LME+Valuation+20260430.pdf"
       class="iconSty file" title="LME Valuation 20260430.pdf 첨부파일 다운로드">첨부파일</a>
</td>
<td class="fileDown">
    <a href="/common/BbsFileDown.do?atchFileId=FILE_000000000032319&FileNm=NHF+Weekly+Metal+Data+20260424.pdf"
       class="iconSty file" title="NHF Weekly Metal Data 20260424.pdf 첨부파일 다운로드">첨부파일</a>
</td>
"""


def test_extract_pdf_links_filters_daily_only():
    links = extract_pdf_links(SAMPLE_HTML)
    assert len(links) == 2
    assert links[0]["date"] == "2026-05-01"
    assert links[0]["file_id"] == "FILE_000000000032340"
    assert "NHF+Daily+Metal+Bulletin" in links[0]["url"]
    assert links[1]["date"] == "2026-04-30"


def test_extract_pdf_links_skips_weekly_and_valuation():
    links = extract_pdf_links(SAMPLE_HTML)
    for link in links:
        assert "Weekly" not in link["url"]
        assert "Valuation" not in link["url"]
