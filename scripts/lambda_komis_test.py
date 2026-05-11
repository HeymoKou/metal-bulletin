"""AWS Lambda KOMIS connectivity + cross-validation probe — stdlib only.

Tests fetching one metal (Cu) daily price via KOMIS BaseMetals ajax endpoint.

Deploy:
  zip -j /tmp/komis_test.zip lambda_komis_test.py
  aws lambda update-function-code --function-name pps-test --region ap-northeast-2 \
    --zip-file fileb:///tmp/komis_test.zip
  aws lambda update-function-configuration --function-name pps-test --region ap-northeast-2 \
    --handler lambda_komis_test.handler

Invoke:
  aws lambda invoke --function-name pps-test --region ap-northeast-2 /tmp/out.json
  cat /tmp/out.json
"""
import http.cookiejar
import json
import urllib.parse
import urllib.request
from urllib.error import HTTPError, URLError

BASE = "https://www.komis.or.kr"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def _public_ip() -> str:
    try:
        with urllib.request.urlopen("https://api.ipify.org", timeout=5) as r:
            return r.read().decode().strip()
    except Exception as e:
        return f"err:{e}"


def handler(event, context):
    result = {"public_ip": _public_ip()}
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    opener.addheaders = [
        ("User-Agent", UA),
        ("Accept-Language", "ko-KR,ko;q=0.9"),
    ]
    # 1. Hit the page to acquire JSESSIONID
    try:
        with opener.open(BASE + "/Komis/RsrcPrice/BaseMetals", timeout=15) as r:
            result["page_status"] = r.status
            result["page_len"] = len(r.read())
            result["cookies"] = [c.name for c in cj]
    except (HTTPError, URLError, ConnectionResetError, OSError) as e:
        result["page_error"] = f"{type(e).__name__}: {e}"
        return result

    # 2. Fetch Cu (MNRL0008) LME CASH (501) daily 2026
    body = urllib.parse.urlencode({
        "mnrkndUnqRadioCd": "MNRL0008",
        "srchMnrkndUnqCd": "MNRL0008",
        "srchPrcCrtr": "501",
        "srchAvgOpt": "DAY",
        "srchField": "year",
        "srchStartDate": "2026",
        "srchEndDate": "2026",
        "lmeInvt": "Y",
    }).encode("utf-8")
    req = urllib.request.Request(
        BASE + "/Komis/RsrcPrice/ajax/getMnrlPrcByMnrkndUnqCd",
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": BASE + "/Komis/RsrcPrice/BaseMetals",
        },
    )
    try:
        with opener.open(req, timeout=15) as r:
            payload = r.read().decode("utf-8", "replace")
        result["ajax_status"] = r.status
        result["ajax_len"] = len(payload)
        try:
            data = json.loads(payload)
            day = (data.get("dataAvg", {}).get("stdMap", {}).get("CRTRYMD") or {})
            result["latest_date"] = day.get("crtrYmd")
            result["latest_cash"] = day.get("cmercPrc")
        except Exception as e:
            result["parse_error"] = str(e)
            result["snippet"] = payload[:300]
    except (HTTPError, URLError, ConnectionResetError, OSError) as e:
        result["ajax_error"] = f"{type(e).__name__}: {e}"

    return result


if __name__ == "__main__":
    print(json.dumps(handler(None, None), ensure_ascii=False, indent=2))
