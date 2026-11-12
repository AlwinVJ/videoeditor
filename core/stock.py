import json
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from core.config import get_pixabay_api_key

PIXABAY_VIDEO_API_URL = "https://pixabay.com/api/videos/"
DEFAULT_REQUEST_TIMEOUT = 12

SEGMENT_COLORS = [
    {"primary": "#8b5cf6", "light": "#c4b5fd", "bg": "rgba(139, 92, 246, 0.18)", "border": "#7c3aed"},  # Violet
    {"primary": "#06b6d4", "light": "#67e8f9", "bg": "rgba(6, 182, 212, 0.18)", "border": "#0891b2"},   # Cyan
    {"primary": "#10b981", "light": "#6ee7b7", "bg": "rgba(16, 185, 129, 0.18)", "border": "#059669"},  # Emerald
    {"primary": "#f59e0b", "light": "#fde68a", "bg": "rgba(245, 158, 11, 0.18)", "border": "#d97706"},  # Amber
    {"primary": "#ec4899", "light": "#fbcfe8", "bg": "rgba(236, 72, 153, 0.18)", "border": "#db2777"},  # Pink
    {"primary": "#3b82f6", "light": "#93c5fd", "bg": "rgba(59, 130, 246, 0.18)", "border": "#2563eb"},  # Blue
]

STOPWORDS = {"in", "on", "at", "to", "for", "of", "and", "the", "a", "an", "is", "it", "with", "by", "as", "or", "from"}


def get_segment_color(segment_index: int) -> Dict[str, str]:
    """Return a distinct, accessible color configuration for a transcript segment index."""
    safe_idx = max(0, int(segment_index or 0))
    return SEGMENT_COLORS[safe_idx % len(SEGMENT_COLORS)]


def calculate_timeline_percentages(
    start: float,
    end: float,
    total_duration: float,
) -> Tuple[float, float]:
    """
    Calculate the left offset and width percentage of a segment along a video timeline.

    Returns:
        (left_percentage, width_percentage) clamped safely between 0% and 100%.
    """
    if not total_duration or total_duration <= 0:
        return 0.0, 0.0

    safe_start = max(0.0, min(total_duration, float(start)))
    safe_end = max(safe_start, min(total_duration, float(end)))

    left_pct = (safe_start / total_duration) * 100.0
    # Minimum width of 2.5% so short segments remain visually perceptible
    raw_width = ((safe_end - safe_start) / total_duration) * 100.0
    width_pct = max(2.5, min(100.0 - left_pct, raw_width))

    return round(left_pct, 2), round(width_pct, 2)


def match_clip_to_transcript(
    clip_keyword: str,
    transcript: Optional[List[Dict[str, Any]]],
) -> Optional[Dict[str, Any]]:
    """
    Find the best matching transcript segment for a stock footage search keyword.

    Args:
        clip_keyword: Search keyword string associated with the stock clip.
        transcript: List of timestamped segment dicts with 'start', 'end', and 'text'.

    Returns:
        Segment match dictionary with 'segment_index', 'start', 'end', 'duration', and 'text',
        or None if no confident match exists.
    """
    if not transcript or not isinstance(transcript, list):
        return None

    cleaned_kw = str(clip_keyword or "").strip().lower()
    if not cleaned_kw:
        return None

    all_tokens = re.findall(r"\b\w+\b", cleaned_kw)
    content_tokens = [w for w in all_tokens if w not in STOPWORDS and len(w) > 2]
    tokens = content_tokens or [w for w in all_tokens if len(w) > 1]
    if not tokens:
        tokens = [cleaned_kw]

    best_segment = None
    best_index = -1
    best_score = 0.0

    for idx, seg in enumerate(transcript):
        if not isinstance(seg, dict):
            continue
        start = seg.get("start")
        end = seg.get("end")
        text = str(seg.get("text", "")).strip()

        if start is None or end is None or float(end) <= float(start):
            continue

        seg_text_lower = text.lower()
        seg_words = set(re.findall(r"\b\w+\b", seg_text_lower))
        score = 0.0

        # Exact phrase match gives highest confidence
        if re.search(r"\b" + re.escape(cleaned_kw) + r"\b", seg_text_lower):
            score = 100.0 + len(cleaned_kw)
        else:
            # Word-level overlap match (whole words only)
            matches = sum(1.0 for t in tokens if t in seg_words)
            if matches > 0:
                score = (matches / len(tokens)) * 10.0

        if score > best_score:
            best_score = score
            best_segment = seg
            best_index = idx

    if best_segment and best_score > 0.0:
        start_val = float(best_segment["start"])
        end_val = float(best_segment["end"])
        return {
            "segment_index": best_index,
            "start": start_val,
            "end": end_val,
            "duration": max(0.1, end_val - start_val),
            "text": str(best_segment.get("text", "")).strip(),
            "score": best_score,
        }

    return None


def format_duration(seconds: float | int) -> str:
    """Format duration in seconds to MM:SS display string."""
    if not seconds or seconds < 0:
        return "00:00"
    total_seconds = int(round(seconds))
    m, s = divmod(total_seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def calculate_clip_placements(
    clips: List[Dict[str, Any]],
    transcript: Optional[List[Dict[str, Any]]] = None,
    total_duration: float = 0.0,
) -> List[Dict[str, Any]]:
    """
    Compute non-overlapping, chronologically ordered timeline intervals for multiple selected B-roll clips.

    Guarantees:
    - Every clip receives a distinct, non-zero visible time slice [start, end].
    - Clips matching the same transcript segment share that segment via non-overlapping sub-intervals.
    - Unmatched clips are assigned non-overlapping time slots across the video timeline.
    - No clip unintentionally occludes or overwrites another clip.

    Args:
        clips: List of standardized stock clip dictionaries.
        transcript: Optional list of timestamped transcript segment dictionaries.
        total_duration: Total duration of original video in seconds.

    Returns:
        List of placement dicts, each with 'clip', 'start', 'end', 'duration', 'segment_index', 'text', 'match'.
    """
    if not clips or not isinstance(clips, list):
        return []

    num_clips = len(clips)
    max_dur = float(total_duration) if total_duration and total_duration > 0 else 0.0

    # 1. Match each clip to transcript
    matches = []
    for c in clips:
        kw = str(c.get("keyword", "")).strip() if isinstance(c, dict) else ""
        m = match_clip_to_transcript(kw, transcript)
        matches.append(m)

    # 2. Fast-path: single clip
    if num_clips == 1:
        c = clips[0]
        m = matches[0]
        c_dur = float(c.get("duration", 0.0) or 0.0) if isinstance(c, dict) else 0.0
        if m:
            s_val = round(float(m["start"]), 2)
            e_val = round(float(m["end"]), 2)
            seg_idx = m["segment_index"]
            seg_text = m.get("text", "")
        else:
            s_val = 0.0
            fallback_len = c_dur if c_dur > 0 else 5.0
            e_val = round(min(max_dur if max_dur > 0 else 5.0, fallback_len), 2)
            if e_val <= s_val:
                e_val = round(s_val + max(0.5, fallback_len), 2)
            seg_idx = 0
            seg_text = "No direct transcript segment match"

        return [{
            "clip": c,
            "start": s_val,
            "end": e_val,
            "duration": round(max(0.1, e_val - s_val), 2),
            "segment_index": seg_idx,
            "text": seg_text,
            "match": m,
        }]

    # 3. Multiple clips: Group clips by segment_index (or None for unmatched)
    from collections import defaultdict
    seg_groups = defaultdict(list)
    unmatched = []

    for idx, (c, m) in enumerate(zip(clips, matches)):
        if m and "segment_index" in m:
            seg_groups[m["segment_index"]].append((idx, c, m))
        else:
            unmatched.append((idx, c))

    placements_by_orig_idx = {}

    # 4. Partition matched segments among clips matching the same segment
    for seg_idx, group in seg_groups.items():
        first_m = group[0][2]
        s_base = float(first_m["start"])
        e_base = float(first_m["end"])
        if max_dur > 0:
            s_base = min(s_base, max_dur)
            e_base = min(e_base, max_dur)
        seg_dur = max(0.2, e_base - s_base)
        group_size = len(group)
        step = seg_dur / group_size

        for j, (orig_idx, c, m) in enumerate(group):
            s_j = round(s_base + (j * step), 2)
            e_j = round(s_base + ((j + 1) * step), 2)
            if e_j <= s_j:
                e_j = round(s_j + 0.1, 2)
            placements_by_orig_idx[orig_idx] = {
                "clip": c,
                "start": s_j,
                "end": e_j,
                "duration": round(e_j - s_j, 2),
                "segment_index": seg_idx,
                "text": m.get("text", ""),
                "match": m,
            }

    # 5. Place unmatched clips into available timeline windows
    if unmatched:
        occupied = sorted([(p["start"], p["end"]) for p in placements_by_orig_idx.values()], key=lambda x: x[0])
        timeline_limit = max_dur if max_dur > 0 else max(5.0, num_clips * 4.0)
        gaps = []
        curr = 0.0
        for s_occ, e_occ in occupied:
            if s_occ > curr + 0.2:
                gaps.append((curr, s_occ))
            curr = max(curr, e_occ)
        if curr + 0.2 < timeline_limit:
            gaps.append((curr, timeline_limit))

        total_gap_dur = sum(g[1] - g[0] for g in gaps)
        if gaps and total_gap_dur >= len(unmatched) * 0.2:
            unm_idx = 0
            for g_start, g_end in gaps:
                g_len = g_end - g_start
                gap_share = max(1, int(round((g_len / total_gap_dur) * len(unmatched))))
                clips_for_gap = unmatched[unm_idx:unm_idx + gap_share]
                unm_idx += len(clips_for_gap)
                if clips_for_gap:
                    step = g_len / len(clips_for_gap)
                    for k, (orig_idx, c) in enumerate(clips_for_gap):
                        s_k = round(g_start + (k * step), 2)
                        e_k = round(g_start + ((k + 1) * step), 2)
                        if e_k <= s_k:
                            e_k = round(s_k + 0.1, 2)
                        placements_by_orig_idx[orig_idx] = {
                            "clip": c,
                            "start": s_k,
                            "end": e_k,
                            "duration": round(e_k - s_k, 2),
                            "segment_index": 0,
                            "text": "Custom timeline placement",
                            "match": None,
                        }
                if unm_idx >= len(unmatched):
                    break

        still_unplaced = [item for item in unmatched if item[0] not in placements_by_orig_idx]
        if still_unplaced:
            if not placements_by_orig_idx:
                step = timeline_limit / len(still_unplaced)
                for k, (orig_idx, c) in enumerate(still_unplaced):
                    s_k = round(k * step, 2)
                    e_k = round((k + 1) * step, 2)
                    if e_k <= s_k:
                        e_k = round(s_k + 0.1, 2)
                    placements_by_orig_idx[orig_idx] = {
                        "clip": c,
                        "start": s_k,
                        "end": e_k,
                        "duration": round(e_k - s_k, 2),
                        "segment_index": 0,
                        "text": "Custom timeline placement",
                        "match": None,
                    }
            else:
                last_end = max((p["end"] for p in placements_by_orig_idx.values()), default=0.0)
                step = 3.0
                for k, (orig_idx, c) in enumerate(still_unplaced):
                    s_k = round(last_end + (k * step), 2)
                    e_k = round(last_end + ((k + 1) * step), 2)
                    placements_by_orig_idx[orig_idx] = {
                        "clip": c,
                        "start": s_k,
                        "end": e_k,
                        "duration": round(e_k - s_k, 2),
                        "segment_index": 0,
                        "text": "Custom timeline placement",
                        "match": None,
                    }

    # Final pass: check if any placements exceed or touch max_dur
    if max_dur > 0 and len(placements_by_orig_idx) > 1:
        items = sorted(placements_by_orig_idx.items(), key=lambda x: (x[1]["start"], x[1]["end"]))
        needs_fit = any(p["start"] >= max_dur - 0.05 or p["end"] > max_dur + 0.05 for _, p in items)
        if needs_fit:
            step = max_dur / len(items)
            for k, (orig_idx, p) in enumerate(items):
                s_k = round(k * step, 2)
                e_k = round((k + 1) * step, 2)
                if e_k <= s_k:
                    e_k = round(s_k + 0.1, 2)
                p["start"] = s_k
                p["end"] = e_k
                p["duration"] = round(e_k - s_k, 2)

    # Final pass: reconstruct list ordered by original clip index
    results = [placements_by_orig_idx[i] for i in range(num_clips)]
    return results


def search_pixabay_videos(
    query: str,
    api_key: Optional[str] = None,
    per_page: int = 6,
    page: int = 1,
    timeout: int = DEFAULT_REQUEST_TIMEOUT,
) -> List[Dict[str, Any]]:
    """
    Search the Pixabay Video API for a single keyword query.

    Args:
        query: The visual search term (e.g. 'modern office', 'city skyline').
        api_key: Optional Pixabay API key. If omitted, retrieved from core.config.
        per_page: Number of results to return per page (Pixabay minimum: 3, maximum: 200).
        page: Page number for pagination (default: 1).
        timeout: Request timeout in seconds.

    Returns:
        List of standardized clip dictionaries.

    Raises:
        ValueError: If query is empty or API key missing.
        PermissionError: If Pixabay authentication fails.
        ConnectionError: If network connection fails.
        TimeoutError: If the request times out.
        RuntimeError: If rate limit exceeded or Pixabay returns an error.
    """
    cleaned_query = str(query or "").strip()
    if not cleaned_query:
        return []

    resolved_key = api_key or get_pixabay_api_key()
    if not resolved_key:
        raise ValueError(
            "Pixabay API key not found. Please ensure 'PIXABAY_API_KEY' is configured in your local .env file "
            "or in Streamlit Cloud Secrets (App Settings -> Secrets)."
        )

    # Pixabay API constraints: q <= 100 characters, per_page between 3 and 200
    safe_query = cleaned_query[:100]
    safe_per_page = max(3, min(200, int(per_page)))
    safe_page = max(1, int(page))

    params = {
        "key": resolved_key,
        "q": safe_query,
        "per_page": safe_per_page,
        "page": safe_page,
        "safesearch": "true",
        "video_type": "all",
    }
    encoded_url = f"{PIXABAY_VIDEO_API_URL}?{urllib.parse.urlencode(params)}"

    req = urllib.request.Request(
        encoded_url,
        headers={"User-Agent": "Mozilla/5.0 (Streamlit-VideoEditor/1.0)"},
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            payload = response.read().decode("utf-8")
            data = json.loads(payload)
    except urllib.error.HTTPError as e:
        error_body = ""
        try:
            error_body = e.read().decode("utf-8", errors="ignore")
        except Exception:
            pass

        if e.code == 400 and ("invalid or missing" in error_body.lower() or "api key" in error_body.lower()):
            raise PermissionError(
                "Pixabay authentication failed. Please check that your PIXABAY_API_KEY in .env or Streamlit Secrets is valid."
            ) from e
        elif e.code == 429:
            raise RuntimeError(
                "Pixabay API rate limit exceeded. Please wait a moment before trying again."
            ) from e
        else:
            raise RuntimeError(f"Pixabay API error ({e.code}): {e.reason}") from e
    except urllib.error.URLError as e:
        if isinstance(e.reason, socket.timeout):
            raise TimeoutError("Pixabay API request timed out. Please try again.") from e
        raise ConnectionError(
            "Could not connect to Pixabay API. Please verify your internet connection."
        ) from e
    except (socket.timeout, TimeoutError) as e:
        raise TimeoutError("Pixabay API request timed out. Please try again.") from e
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse Pixabay API response: {str(e)}") from e
    except Exception as e:
        raise RuntimeError(f"Stock footage search failed: {str(e)}") from e

    hits = data.get("hits", [])
    results: List[Dict[str, Any]] = []

    for hit in hits:
        if not isinstance(hit, dict):
            continue

        videos_dict = hit.get("videos", {}) or {}

        # Best resolution stream for eventual B-roll placement (large > medium > small > tiny)
        best_stream = (
            videos_dict.get("large")
            or videos_dict.get("medium")
            or videos_dict.get("small")
            or videos_dict.get("tiny")
            or {}
        )

        # Lightweight stream for fast inline web preview (tiny > small > medium)
        preview_stream = (
            videos_dict.get("tiny")
            or videos_dict.get("small")
            or videos_dict.get("medium")
            or best_stream
        )

        # Best thumbnail URL
        thumbnail_url = (
            (videos_dict.get("medium") or {}).get("thumbnail")
            or (videos_dict.get("small") or {}).get("thumbnail")
            or (videos_dict.get("tiny") or {}).get("thumbnail")
            or best_stream.get("thumbnail")
            or ""
        )

        width = best_stream.get("width", 0)
        height = best_stream.get("height", 0)
        duration_sec = hit.get("duration", 0)

        results.append(
            {
                "id": hit.get("id"),
                "tags": hit.get("tags", ""),
                "duration": duration_sec,
                "duration_formatted": format_duration(duration_sec),
                "width": width,
                "height": height,
                "resolution": f"{width}×{height}" if width and height else "HD",
                "thumbnail_url": thumbnail_url,
                "preview_url": preview_stream.get("url", ""),
                "download_url": best_stream.get("url", ""),
                "page_url": hit.get("pageURL", ""),
                "user": hit.get("user", ""),
                "keyword": cleaned_query,
            }
        )

    return results


def search_stock_footage(
    keywords: List[str],
    api_key: Optional[str] = None,
    max_results: int = 12,
) -> List[Dict[str, Any]]:
    """
    Search stock footage across multiple AI-generated keywords, aggregating and deduplicating results.

    Args:
        keywords: List of visual keyword strings from Card 2.
        api_key: Optional Pixabay API key override.
        max_results: Target maximum number of unique video clips to return.

    Returns:
        List of unique, deduplicated clip dictionaries.

    Raises:
        ValueError: If no valid keywords are provided.
        PermissionError: If API key is invalid.
        ConnectionError: If network request fails.
        TimeoutError: If request times out.
        RuntimeError: If rate limit or other API failure occurs.
    """
    if not keywords or not isinstance(keywords, list):
        raise ValueError(
            "Please generate AI keywords in Step 2 before searching for stock footage."
        )

    # Filter and clean keywords, preserving order
    clean_terms = []
    seen_terms = set()
    for kw in keywords:
        cleaned = str(kw or "").strip()
        if cleaned and cleaned.lower() not in seen_terms:
            seen_terms.add(cleaned.lower())
            clean_terms.append(cleaned)

    if not clean_terms:
        raise ValueError(
            "Please generate AI keywords in Step 2 before searching for stock footage."
        )

    # Take up to top 4 keywords to balance variety, latency, and API rate limits
    terms_to_search = clean_terms[:4]
    per_keyword_count = max(3, min(8, (max_results // len(terms_to_search)) + 1))

    aggregated_results: List[Dict[str, Any]] = []
    seen_ids = set()

    for term in terms_to_search:
        clips = search_pixabay_videos(
            query=term,
            api_key=api_key,
            per_page=per_keyword_count,
        )
        for clip in clips:
            clip_id = clip.get("id")
            if clip_id and clip_id not in seen_ids:
                seen_ids.add(clip_id)
                aggregated_results.append(clip)
                if len(aggregated_results) >= max_results:
                    break

        if len(aggregated_results) >= max_results:
            break

    return aggregated_results
