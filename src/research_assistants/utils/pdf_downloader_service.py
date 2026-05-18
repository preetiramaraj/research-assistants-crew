from __future__ import annotations

import os
import re
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from research_assistants.utils.logging_config import setup_file_logger

# This module implements the deterministic, testable core of the PDF downloading step.
# It parses `results/literature_review.md`, resolves a best-effort PDF URL per paper,
# downloads PDFs to disk, and produces a markdown report.

logger = setup_file_logger(
    __name__,
    Path(__file__).resolve().parents[1] / "logs" / "pdf_download.log"
)


@dataclass(frozen=True)
class PaperEntry:
    """A single paper record parsed from `results/literature_review.md`.

    Fields map 1:1 to the labeled lines enforced by the literature review task output.
    """

    title: str
    authors: str
    year: str
    doi: str
    arxiv: str
    link: str
    open_access_pdf: str


_ARXIV_ID_RE = re.compile(r"(?i)(?:arxiv:)?\s*([0-9]{4}\.[0-9]{4,5})(?:v\d+)?")
_DOI_RE = re.compile(r"(?i)\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b")


def _clean_value(value: str) -> str:
    """Normalize a parsed field value from markdown."""
    return value.strip().strip("` ").strip()


def parse_literature_review_markdown(md_text: str) -> list[PaperEntry]:
    """Parse `results/literature_review.md` into PaperEntry records.

    The parser expects each paper to contain labeled fields (order doesn't matter):
    Title:, Authors:, Year:, DOI:, arXiv:, Link:

    It is intentionally simple and line-based for readability and robustness.
    """

    current: dict[str, str] = {}
    papers: list[PaperEntry] = []

    def flush() -> None:
        nonlocal current
        if not current:
            return

        title = current.get("title", "").strip()
        if not title:
            current = {}
            return

        papers.append(
            PaperEntry(
                title=title,
                authors=current.get("authors", "N/A").strip(),
                year=current.get("year", "N/A").strip(),
                doi=current.get("doi", "N/A").strip(),
                arxiv=current.get("arxiv", "N/A").strip(),
                link=current.get("link", "N/A").strip(),
                open_access_pdf=current.get("open access pdf", "N/A").strip(),
            )
        )
        current = {}

    for raw_line in md_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # Allow headings like "### Paper 1" to separate entries.
        if line.startswith("### "):
            flush()
            continue

        # Normalize list formatting: "- Title: ..." or "**Title:** ..."
        normalized = line.lstrip("- ")
        normalized = re.sub(r"^\*\*(.+?)\*\*\s*:?\s*", r"\1: ", normalized)

        m = re.match(r"^(Title|Authors|Year|DOI|arXiv|Link|Open Access PDF)\s*:\s*(.*)$", normalized, flags=re.IGNORECASE)
        if m:
            key = m.group(1).lower()
            value = _clean_value(m.group(2))
            current[key] = value
            continue

    flush()
    return papers


def extract_doi(text: str) -> Optional[str]:
    """Extract a DOI from free-form text (if present)."""
    m = _DOI_RE.search(text or "")
    return m.group(0) if m else None


def extract_arxiv_id(text: str) -> Optional[str]:
    """Extract an arXiv ID from free-form text (if present)."""
    m = _ARXIV_ID_RE.search(text or "")
    return m.group(1) if m else None


def arxiv_pdf_url(arxiv_id: str) -> str:
    """Construct the canonical arXiv PDF URL for an arXiv ID."""
    return f"https://arxiv.org/pdf/{arxiv_id}.pdf"


def _is_direct_pdf(url: str, session: requests.Session) -> bool:
    """Check if a URL directly returns PDF content.

    Uses HEAD request first, then falls back to GET with byte check.
    """
    try:
        # Try HEAD request first
        resp = session.head(url, timeout=10, allow_redirects=True)
        #print(f"[DEBUG] HEAD request status: {resp.status_code if hasattr(resp, 'status_code') else resp.ok}")
        #print(f"[DEBUG] URL: {url} HEAD content-type: {resp.headers.get('content-type', 'N/A')}")
        if resp.ok:
            content_type = resp.headers.get('content-type', '').lower()
            if 'pdf' in content_type:
                return True
    except Exception as e:
        #print(f"[DEBUG] HEAD request failed: {e}")
        pass

    try:
        # Fallback: GET request and check first bytes
        resp = session.get(url, stream=True, timeout=10, allow_redirects=True)
        #print(f"[DEBUG]  URL: {url} GET request status: {resp.status_code if hasattr(resp, 'status_code') else resp.ok}")
        if resp.ok:
            first_bytes = resp.raw.read(5)
            #print(f"[DEBUG]  URL: {url}  First bytes: {first_bytes}")
            if first_bytes == b"%PDF-":
                return True
    except Exception as e:
        #print(f"[DEBUG] URL: {url}  GET request failed: {e}")
        pass

    return False


def _scrape_pdf_link(url: str, session: requests.Session) -> Optional[str]:
    """Scrape an HTML page to find PDF links.

    Looks for <a> tags with href ending in .pdf, ignoring query parameters.
    Returns the first valid PDF link found.
    """
    try:
        resp = session.get(url, timeout=15, allow_redirects=True)
        if not resp.ok or not resp.text:
            return None

        soup = BeautifulSoup(resp.text, 'html.parser')

        # Look for links ending with .pdf (ignoring query parameters)
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            parsed = urlparse(href)
            path = parsed.path.lower()

            if path.endswith('.pdf'):
                # Convert relative URLs to absolute
                if href.startswith('http'):
                    pdf_url = href
                else:
                    base_url = f"{resp.url.rsplit('/', 1)[0]}"
                    pdf_url = f"{base_url}/{href.lstrip('/')}"

                # Validate the scraped link
                if _is_direct_pdf(pdf_url, session):
                    return pdf_url

        # Fallback: look for common PDF link patterns
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href'].lower()
            text = a_tag.get_text().lower()
            if any(keyword in href or keyword in text for keyword in ['download', 'fulltext', 'pdf']):
                if href.endswith('.pdf') or '.pdf' in href:
                    if href.startswith('http'):
                        pdf_url = a_tag['href']
                    else:
                        base_url = f"{resp.url.rsplit('/', 1)[0]}"
                        pdf_url = f"{base_url}/{a_tag['href'].lstrip('/')}"
                    
                    if _is_direct_pdf(pdf_url, session):
                        return pdf_url

    except Exception:
        pass

    return None


def _validate_and_scrape_pdf_url(url: str, session: requests.Session) -> Optional[str]:
    """Validate if URL returns PDF, with HTML scraping fallback.

    Args:
        url: The URL to validate
        session: Requests session with appropriate headers

    Returns:
        The validated PDF URL, or None if validation fails
    """
    #print(f"[DEBUG] Validating URL: {url}")
    # Try direct PDF validation first
    if _is_direct_pdf(url, session):
        #print(f"[DEBUG] Direct PDF validation succeeded for: {url}")
        return url

    #print(f"[DEBUG] Direct PDF validation failed, trying HTML scraping for: {url}")
    # Fallback: scrape HTML for PDF links
    scraped = _scrape_pdf_link(url, session)
    #print(f"[DEBUG] Scraping result: {scraped}")
    return scraped


def _safe_filename(value: str) -> str:
    """Make a reasonably safe filename for Windows/macOS/Linux."""
    value = re.sub(r"\s+", " ", value).strip()
    value = re.sub(r"[\\/:*?\"<>|]", "_", value)
    value = re.sub(r"[^\w\s().,-]", "", value)
    value = value.strip(" ._")
    return value[:180] if len(value) > 180 else value


def _choose_filename(paper: PaperEntry) -> str:
    """Pick a stable output filename for a paper (prefer title; fallback to DOI/arXiv)."""
    if paper.title and paper.title != "N/A":
        return _safe_filename(paper.title) + ".pdf"

    if paper.doi and paper.doi != "N/A":
        return _safe_filename(paper.doi) + ".pdf"

    arxiv_id = extract_arxiv_id(paper.arxiv)
    if arxiv_id:
        return f"arxiv_{arxiv_id}.pdf"

    return "paper.pdf"


def _ensure_unique_path(path: Path) -> Path:
    """If `path` exists, generate a `-N` suffixed path that does not exist."""
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    for i in range(1, 1000):
        candidate = path.with_name(f"{stem}-{i}{suffix}")
        if not candidate.exists():
            return candidate

    raise RuntimeError(f"Could not find available filename for {path}")


def resolve_pdf_url(
    paper: PaperEntry,
    session: requests.Session,
    *,
    unpaywall_email: Optional[str] = None,
) -> Optional[str]:
    """Resolve an OA PDF URL for a paper.

    Priority:
      1) Open Access PDF field from semantic scholar
      2) arXiv id -> arXiv PDF URL
      3) DOI -> Unpaywall
    """
    #print(f"[DEBUG] Paper title: {paper.title}")
    # Priority 1: Open Access PDF field from semantic scholar
    open_access_pdf = (paper.open_access_pdf or "").strip()
    if open_access_pdf and open_access_pdf != "N/A":
        if open_access_pdf.startswith(("http://", "https://")):
            validated_url = _validate_and_scrape_pdf_url(open_access_pdf, session)
            if validated_url:
                return validated_url

    # Priority 2: arXiv id
    arxiv_id = extract_arxiv_id(paper.arxiv) or extract_arxiv_id(paper.link)
    if arxiv_id:
        return arxiv_pdf_url(arxiv_id)

    # Priority 3: DOI -> Unpaywall
    doi = extract_doi(paper.doi) or extract_doi(paper.link)

    if doi and unpaywall_email:
        try:
            url = f"https://api.unpaywall.org/v2/{doi}"
            resp = session.get(url, params={"email": unpaywall_email}, timeout=20)
            if resp.ok:
                data = resp.json()
                best = (data.get("best_oa_location") or {})
                pdf_url = best.get("url_for_pdf") or best.get("url")
                if isinstance(pdf_url, str) and pdf_url:
                    # Validate the Unpaywall URL with HTML scraping fallback
                    validated_url = _validate_and_scrape_pdf_url(pdf_url, session)
                    if validated_url:
                        return validated_url
        except Exception:
            pass


    return None


def download_pdf(
    pdf_url: str,
    out_path: Path,
    session: requests.Session,
) -> None:
    """Download a PDF URL to disk, validating the content looks like a PDF."""
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with session.get(pdf_url, stream=True, timeout=40) as resp:
        resp.raise_for_status()
        # Read a small chunk to validate it is a PDF.
        first = resp.raw.read(5)
        if first != b"%PDF-":
            # Fallback: some servers don't support streaming properly; check full content.
            content = first + resp.content
            if not content.startswith(b"%PDF-"):
                raise ValueError(f"URL did not return a PDF: {pdf_url}")
            out_path.write_bytes(content)
            return

        with out_path.open("wb") as f:
            f.write(first)
            for chunk in resp.iter_content(chunk_size=1024 * 64):
                if chunk:
                    f.write(chunk)


@dataclass(frozen=True)
class DownloadResult:
    """Outcome of attempting to download a single paper PDF."""

    paper: PaperEntry
    status: str  # downloaded | skipped | failed
    pdf_url: str
    file_path: str
    reason: str


def download_pdfs_from_markdown(
    md_path: Path,
    save_dir: Path,
    *,
    max_papers: Optional[int] = None,
    overwrite: bool = False,
    dry_run: bool = False,
    session: Optional[requests.Session] = None,
) -> list[DownloadResult]:
    """Parse a literature review markdown file and download PDFs for listed papers.

    - Respects local caching unless `overwrite=True`.
    - Uses Unpaywall only if `UNPAYWALL_EMAIL` is set in the environment.
    """
    md_text = md_path.read_text(encoding="utf-8")
    papers = parse_literature_review_markdown(md_text)

    if max_papers is not None:
        papers = papers[: max_papers]

    save_dir.mkdir(parents=True, exist_ok=True)

    sess = session or requests.Session()
    # Add browser-like headers to avoid basic bot detection
    if not session:
        sess.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
    unpaywall_email = os.environ.get("UNPAYWALL_EMAIL")

    results: list[DownloadResult] = []

    for paper in papers:
        try:
            pdf_url = resolve_pdf_url(paper, sess, unpaywall_email=unpaywall_email)
            if not pdf_url:
                results.append(
                    DownloadResult(
                        paper=paper,
                        status="failed",
                        pdf_url="",
                        file_path="",
                        reason="No PDF URL could be resolved",
                    )
                )
                continue

            filename = _choose_filename(paper)
            out_path = save_dir / filename

            if out_path.exists() and not overwrite:
                results.append(
                    DownloadResult(
                        paper=paper,
                        status="skipped",
                        pdf_url=pdf_url,
                        file_path=str(out_path),
                        reason="File already exists",
                    )
                )
                continue

            if out_path.exists() and overwrite:
                out_path.unlink()

            out_path = _ensure_unique_path(out_path)

            if dry_run:
                results.append(
                    DownloadResult(
                        paper=paper,
                        status="skipped",
                        pdf_url=pdf_url,
                        file_path=str(out_path),
                        reason="Dry run",
                    )
                )
                continue

            download_pdf(pdf_url, out_path, sess)
            results.append(
                DownloadResult(
                    paper=paper,
                    status="downloaded",
                    pdf_url=pdf_url,
                    file_path=str(out_path),
                    reason="",
                )
            )
        except Exception as e:
            results.append(
                DownloadResult(
                    paper=paper,
                    status="failed",
                    pdf_url="",
                    file_path="",
                    reason=str(e),
                )
            )

    return results


def format_download_report_md(results: Iterable[DownloadResult]) -> str:
    """Convert download results to a human-readable markdown report."""
    results_list = list(results)

    downloaded = sum(1 for r in results_list if r.status == "downloaded")
    skipped = sum(1 for r in results_list if r.status == "skipped")
    failed = sum(1 for r in results_list if r.status == "failed")

    lines: list[str] = []
    lines.append("#### PDF Download Report")
    lines.append("")
    lines.append(f"Downloaded: {downloaded}")
    lines.append(f"Skipped: {skipped}")
    lines.append(f"Failed: {failed}")
    lines.append("")

    for i, r in enumerate(results_list, start=1):
        lines.append(f"##### {i}. {r.paper.title}")
        lines.append("")
        lines.append(f"Status: {r.status}")
        if r.pdf_url:
            lines.append(f"PDF URL: {r.pdf_url}")
        if r.file_path:
            lines.append(f"Saved to: {r.file_path}")
        if r.reason:
            lines.append(f"Reason: {r.reason}")
        lines.append("")

    return "\n".join(lines)


def run_pdf_download(
    md_path: str = None,
    save_dir: str = None,
    output_report: str = None,
    max_papers: Optional[int] = None,
    overwrite: bool = False,
    dry_run: bool = False,
) -> None:
    """
    Run PDF download by parsing literature_review.md and downloading PDFs for listed papers.
    
    Args:
        md_path: Path to literature_review.md file
        save_dir: Directory to save PDFs
        output_report: Path to write download_report.md
        max_papers: Optional cap on number of papers to process
        overwrite: If true, overwrite existing PDFs
        dry_run: If true, do not download; only report what would be done
    """
    # Set default paths relative to project root
    if md_path is None:
        md_path = str(Path(__file__).resolve().parents[3] / "results" / "literature_review.md")
    if save_dir is None:
        save_dir = str(Path(__file__).resolve().parents[3] / "lit_review_pdfs")
    if output_report is None:
        output_report = str(Path(__file__).resolve().parents[3] / "results" / "download_report.md")
    
    logger.info(f"Starting PDF download from {md_path}")
    logger.info(f"Saving PDFs to {save_dir}")
    
    try:
        results = download_pdfs_from_markdown(
            md_path=Path(md_path),
            save_dir=Path(save_dir),
            max_papers=max_papers,
            overwrite=overwrite,
            dry_run=dry_run,
        )
        
        # Format and write report
        report_md = format_download_report_md(results)
        output_file = Path(output_report)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report_md)
        
        downloaded = sum(1 for r in results if r.status == "downloaded")
        skipped = sum(1 for r in results if r.status == "skipped")
        failed = sum(1 for r in results if r.status == "failed")
        
        logger.info(f"PDF download complete: {downloaded} downloaded, {skipped} skipped, {failed} failed")
        logger.info(f"Download report written to {output_report}")
        
    except Exception as e:
        logger.error(f"Error during PDF download: {e}")
        raise
