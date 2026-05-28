"""OKCountyRecords API client with charge estimation and approval gating."""

import os
import time
from dataclasses import dataclass
from typing import Optional

import requests

from core.config import config
from core.audit import record
from core.database import track_cost


@dataclass
class SearchResult:
    document_id: str
    county: str
    book: str
    page: str
    instrument_number: str
    instrument_type: str
    recording_date: str
    download_url: str
    estimated_cost: float


@dataclass
class DownloadResult:
    success: bool
    file_path: str
    file_size_bytes: int
    actual_charge: float
    error: Optional[str] = None


class OKCountyClient:
    def __init__(self):
        self.api_key = os.getenv("OKCOUNTY_API_KEY", "")
        self.base_url = config.OKCOUNTY_API_BASE_URL.rstrip("/")
        self.cost_per_image = config.OKCOUNTY_COST_PER_IMAGE
        self.cost_per_search = config.OKCOUNTY_COST_PER_SEARCH
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "User-Agent": "DOTO-Image-Commander/1.0",
        })

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key != "your_api_key_here")

    def reload_key(self) -> None:
        self.api_key = os.getenv("OKCOUNTY_API_KEY", "")
        self._session.headers["Authorization"] = f"Bearer {self.api_key}"

    def estimate_batch_cost(self, n_images: int, n_searches: int = 0) -> dict:
        image_cost = n_images * self.cost_per_image
        search_cost = n_searches * self.cost_per_search
        return {
            "images": n_images,
            "searches": n_searches,
            "image_cost": image_cost,
            "search_cost": search_cost,
            "total": image_cost + search_cost,
        }

    def search_document(self, county: str, book: str = None, page: str = None,
                        instrument_number: str = None, image_number: str = None,
                        instrument_type: str = None) -> Optional[SearchResult]:
        """Query the API for a document. Returns None if not found."""
        if not self.is_configured():
            raise RuntimeError("OKCountyRecords API key not configured.")

        params = {"county": county}
        if book:
            params["book"] = book
        if page:
            params["page"] = page
        if instrument_number:
            params["instrument_number"] = instrument_number
        if image_number:
            params["image_number"] = image_number
        if instrument_type:
            params["instrument_type"] = instrument_type

        record("api_search", f"Searching {county} {book}/{page} {instrument_number}",
               data=params, api_called="okcounty/search", cost=self.cost_per_search)
        track_cost("okcounty", self.cost_per_search,
                   f"Search: {county} {book}/{page} {instrument_number}")

        try:
            resp = self._session.get(f"{self.base_url}/documents/search",
                                     params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            if not data.get("results"):
                return None
            r = data["results"][0]
            return SearchResult(
                document_id=str(r.get("id", "")),
                county=r.get("county", county),
                book=r.get("book", book or ""),
                page=r.get("page", page or ""),
                instrument_number=r.get("instrument_number", instrument_number or ""),
                instrument_type=r.get("instrument_type", instrument_type or ""),
                recording_date=r.get("recording_date", ""),
                download_url=r.get("download_url", ""),
                estimated_cost=self.cost_per_image,
            )
        except requests.HTTPError as e:
            record("api_error", f"Search failed: {e}", api_called="okcounty/search")
            raise

    def download_document(self, document_id: str, dest_path: str,
                          queue_item_id: int = None) -> DownloadResult:
        """Download a PDF document to dest_path. Audit-logs the transaction."""
        if not self.is_configured():
            raise RuntimeError("OKCountyRecords API key not configured.")

        record("api_download_start", f"Downloading document {document_id}",
               api_called="okcounty/download", cost=self.cost_per_image)

        try:
            resp = self._session.get(
                f"{self.base_url}/documents/{document_id}/download",
                timeout=60, stream=True,
            )
            resp.raise_for_status()
            size = 0
            with open(dest_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    f.write(chunk)
                    size += len(chunk)

            actual_charge = float(resp.headers.get("X-Charge", self.cost_per_image))
            track_cost("okcounty", actual_charge,
                       f"Download: {document_id}", queue_item_id=queue_item_id)
            record("api_download_success", f"Downloaded {document_id} ({size} bytes)",
                   data={"dest": dest_path, "size": size},
                   api_called="okcounty/download", cost=actual_charge)
            return DownloadResult(success=True, file_path=dest_path,
                                  file_size_bytes=size, actual_charge=actual_charge)

        except Exception as e:
            record("api_download_error", f"Download failed for {document_id}: {e}",
                   api_called="okcounty/download")
            return DownloadResult(success=False, file_path=dest_path,
                                  file_size_bytes=0, actual_charge=0.0, error=str(e))

    def download_by_url(self, url: str, dest_path: str,
                        queue_item_id: int = None) -> DownloadResult:
        """Download from a pre-authorized URL (returned by search)."""
        record("api_download_start", f"Downloading via URL -> {dest_path}",
               api_called="okcounty/download_url", cost=self.cost_per_image)
        try:
            resp = self._session.get(url, timeout=60, stream=True)
            resp.raise_for_status()
            size = 0
            with open(dest_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    f.write(chunk)
                    size += len(chunk)
            actual_charge = float(resp.headers.get("X-Charge", self.cost_per_image))
            track_cost("okcounty", actual_charge,
                       f"Download URL: {dest_path}", queue_item_id=queue_item_id)
            record("api_download_success", f"Downloaded ({size} bytes) -> {dest_path}",
                   api_called="okcounty/download_url", cost=actual_charge)
            return DownloadResult(success=True, file_path=dest_path,
                                  file_size_bytes=size, actual_charge=actual_charge)
        except Exception as e:
            record("api_download_error", f"URL download failed: {e}",
                   api_called="okcounty/download_url")
            return DownloadResult(success=False, file_path=dest_path,
                                  file_size_bytes=0, actual_charge=0.0, error=str(e))


# Module-level singleton
client = OKCountyClient()
