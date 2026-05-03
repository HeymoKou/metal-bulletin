# LME Non-Ferrous Metals Price API Research

**Date**: 2026-05-03  
**Target Metals**: Copper, Aluminum, Zinc, Nickel, Lead, Tin  
**Goal**: Real-time or near-real-time LME futures price data via API

---

## Category 1: LME Official Data

### LME Market Data Services

LME's official website (lme.com) blocks automated access (403), but based on available documentation:

**Products:**
- **LMEsmart**: LME's official electronic data platform providing real-time and delayed market data
- **LME Select**: FIX-based electronic trading platform (since 2001), handles majority of LME business
- **LME DataScope**: Historical data download service
- **Real-time Market Data Feed**: Distributed via authorized third-party vendors

**Access Methods:**
- Direct market data feed (requires LME membership/license agreement)
- Via authorized third-party data vendors (Refinitiv/LSEG, Bloomberg, etc.)
- FIX protocol for trading

**Pricing:**
- Enterprise-level pricing (not publicly disclosed)
- Estimated: $10,000-$50,000+/year for direct real-time feed
- Redistributor licenses additional cost

**Key Notes:**
- LME restricts free redistribution of real-time prices
- 15-minute delayed data available through some vendors
- Official settlement prices (published daily at ~12:35 London time) are the benchmark

---

## Category 2: Major Financial Data APIs

### 1. Metals-API (metals-api.com) — BEST MATCH

| Attribute | Details |
|-----------|---------|
| **Coverage** | All 6 LME metals: Cu (LME-XCU), Al (LME-ALU), Zn (LME-ZNC), Ni (LME-NI), Pb (LME-LEAD), Sn (LME-TIN) |
| **Data Types** | Cash (CS), 3-Month (3M), Stocks (ST) |
| **3M Symbols** | XCU3M, ALU3M, NI3M, LEAD3M (Zn and Sn: Cash only) |
| **Latency** | 60-second updates (higher tiers), 10-minute (entry tier) |
| **Price** | $19.99/mo (Copper plan) to $999/mo (Rhodium); Enterprise $25,000/yr |
| **Format** | REST API, JSON responses |
| **Auth** | API key (access_key parameter) |
| **LME Inventory** | Yes — ST (Stock) data type available |
| **Python** | `pip install metals-api` (v0.4) |
| **Historical** | LME data from 2008 onwards |
| **Endpoints** | Latest, Historical, Time-Series, Fluctuation, OHLC, Convert, Historical LME |
| **URL** | https://metals-api.com |

### 2. Commodities-API (commodities-api.com)

| Attribute | Details |
|-----------|---------|
| **Coverage** | All 6 LME metals: LME-XCU, LME-ALU, LME-ZNC, LME-NI, LME-LEAD, LME-TIN |
| **Data Types** | Cash and 3M (XCU3M, ALU3M, NI3M, LEAD3M) |
| **Latency** | 60-second to 10-minute updates depending on plan |
| **Price** | $499.99/yr (PRO, 1,000 calls/mo) to $49,400/yr (Premium, 1M calls/mo). No free tier. 7-day trial. |
| **Format** | REST API, JSON |
| **Auth** | API key |
| **LME Inventory** | Not mentioned |
| **Python** | Not found |
| **Historical** | Back to 1969 (varies by symbol) |
| **Endpoints** | Latest, Historical, Convert, Time-Series, Fluctuation, OHLC, News |
| **URL** | https://commodities-api.com |

### 3. MetalpriceAPI (metalpriceapi.com)

| Attribute | Details |
|-----------|---------|
| **Coverage** | 20+ metals including Copper (USDXCU), Zinc (USDZNC), others |
| **Data Types** | Spot prices; LME-specific Cash/3M not explicitly confirmed |
| **Latency** | Delayed market data (frequency unclear); Hourly endpoint available |
| **Price** | Free tier available (limited); paid plans not detailed publicly |
| **Format** | REST API, JSON |
| **Auth** | API key |
| **LME Inventory** | Not available |
| **Python** | `pip install metalpriceapi` (MIT license) |
| **Endpoints** | fetchLive, fetchHistorical, hourly, fetchOHLC, convert, timeframe, change, carat |
| **URL** | https://metalpriceapi.com |

### 4. Alpha Vantage

| Attribute | Details |
|-----------|---------|
| **Coverage** | Copper and Aluminum only (no Zinc, Nickel, Lead, Tin) |
| **Data Types** | Monthly/quarterly global average prices (NOT LME-specific) |
| **Latency** | EOD/Monthly only — NOT real-time |
| **Price** | Free tier: 25 calls/day; Premium: $49.99/mo (unlimited) |
| **Format** | REST API, JSON/CSV |
| **Auth** | API key |
| **LME Inventory** | No |
| **Python** | `pip install alpha_vantage` |
| **Data Source** | IMF/World Bank global commodity prices (not direct LME feed) |
| **Limitation** | Unit: $/metric ton, monthly interval only. Data from 1992. |
| **URL** | https://www.alphavantage.co |

### 5. Twelve Data

| Attribute | Details |
|-----------|---------|
| **Coverage** | Copper confirmed; other LME base metals unclear |
| **Data Types** | Likely spot/futures — specific LME Cash/3M not confirmed |
| **Latency** | REST: minutely updates; WebSocket: 170ms latency |
| **Price** | Free (8 API credits/day); Grow $79/mo; Pro $229/mo; Ultra $999/mo |
| **Format** | REST + WebSocket, JSON/CSV |
| **Auth** | API key |
| **LME Inventory** | No |
| **Python** | `pip install twelvedata` |
| **Note** | Commodities available from Grow tier ($79/mo) and above |
| **URL** | https://twelvedata.com |

### 6. Yahoo Finance (via yfinance)

| Attribute | Details |
|-----------|---------|
| **Coverage** | COMEX Copper (HG=F), COMEX Aluminum (ALI=F) — NOT LME contracts |
| **Data Types** | Futures OHLCV |
| **Latency** | 15-minute delayed quotes |
| **Price** | Free (unofficial API, no guarantee of stability) |
| **Format** | Python library returns pandas DataFrames |
| **Auth** | None required |
| **LME Inventory** | No |
| **Python** | `pip install yfinance` |
| **Limitation** | These are COMEX contracts, NOT LME. No direct LME data on Yahoo Finance. Limited to Cu and Al. |
| **URL** | https://finance.yahoo.com |

### 7. Polygon.io (now Massive.com)

| Attribute | Details |
|-----------|---------|
| **Coverage** | Appears to have pivoted/rebranded to Massive.com |
| **Status** | All polygon.io URLs redirect to massive.com; commodity data availability unclear |
| **Note** | Previously focused on US equities/options/forex. Commodity coverage was limited. |

### 8. Nasdaq Data Link (formerly Quandl)

| Attribute | Details |
|-----------|---------|
| **Coverage** | Previously had LME database (code: "LME") |
| **Status** | LME datasets appear to have been discontinued or moved to premium tier |
| **Historical** | CHRIS (Continuous Futures) database previously included LME contracts |
| **Format** | REST API, JSON/CSV |
| **Auth** | API key |
| **Python** | `pip install nasdaq-data-link` (formerly `quandl`) |
| **Note** | Many free commodity datasets have been deprecated. Premium databases cost $100-$10,000+/year. |
| **URL** | https://data.nasdaq.com |

### 9. Refinitiv/LSEG (London Stock Exchange Group)

| Attribute | Details |
|-----------|---------|
| **Coverage** | All LME metals — comprehensive (as LME is owned by HKEX, LSEG is authorized redistributor) |
| **Data Types** | Cash, 3M, all prompt dates, official settlement prices, inventory |
| **Latency** | Real-time (tick-by-tick) |
| **Price** | Enterprise pricing: estimated $2,000-$25,000+/month depending on scope |
| **Format** | REST API (Refinitiv Data Platform), WebSocket, FIX |
| **Auth** | OAuth 2.0 |
| **LME Inventory** | Yes — full warehouse stocks by location |
| **Python** | `pip install refinitiv-data` or `pip install eikon` |
| **Note** | Industry standard for institutional metals trading. Formerly Thomson Reuters Eikon. |
| **URL** | https://www.lseg.com/en/data-analytics |

### 10. Bloomberg

| Attribute | Details |
|-----------|---------|
| **Coverage** | All LME metals — comprehensive |
| **Data Types** | Cash, 3M, all prompt dates, settlement, inventory, spreads |
| **Latency** | Real-time (tick-by-tick) |
| **Price** | Bloomberg Terminal: ~$24,000/year per seat; Bloomberg B-PIPE (data feed): separate enterprise license |
| **Format** | Bloomberg API (BLPAPI), REST (Bloomberg Enterprise), FIX |
| **Auth** | Terminal license / Enterprise agreement |
| **LME Inventory** | Yes — full warehouse data |
| **Python** | `pip install blpapi` (requires Terminal/B-PIPE license) |
| **Tickers** | LMCADS03 (Cu Cash), LMAHDS03 (Al Cash), LMZSDS03 (Zn Cash), LMNIDS03 (Ni Cash), LMPBDS03 (Pb Cash), LMSNDS03 (Sn Cash) |
| **URL** | https://www.bloomberg.com/professional |

---

## Category 3: Specialized Commodity APIs

### Fastmarkets (formerly Metal Bulletin)

| Attribute | Details |
|-----------|---------|
| **Coverage** | 900+ global metal prices; includes LME base metals |
| **Data Types** | LME official prices, premiums, physical market prices |
| **Latency** | Near real-time for some; daily for official prices |
| **Price** | Enterprise pricing (not public); estimated $5,000-$30,000/year |
| **Format** | REST API, Excel Add-in, Mobile app |
| **Auth** | Enterprise license |
| **LME Inventory** | Likely yes (comprehensive metals coverage) |
| **Python** | No official library found |
| **Note** | Industry standard for physical metals pricing. 200+ price reporters globally. Over 90% forecast accuracy claimed. |
| **URL** | https://www.fastmarkets.com |

### World Bank Commodity Prices

| Attribute | Details |
|-----------|---------|
| **Coverage** | Copper, Aluminum, Zinc, Nickel, Lead, Tin (global averages) |
| **Data Types** | Monthly/annual averages |
| **Latency** | Monthly updates (Pink Sheet) |
| **Price** | Free |
| **Format** | PDF, Excel downloads — NO API |
| **LME Inventory** | No |
| **Limitation** | Monthly frequency only, no real-time or daily data |
| **URL** | https://www.worldbank.org/en/research/commodity-markets |

---

## Category 4: Korean Sources

### KRX (한국거래소) Open API

| Attribute | Details |
|-----------|---------|
| **Coverage** | Gold futures only on KRX commodity market; NO base metals (Cu, Al, Zn, Ni, Pb, Sn) |
| **Status** | KRX does not list non-ferrous metals futures |
| **URL** | https://openapi.krx.co.kr |

### Bank of Korea ECOS API (한국은행 경제통계시스템)

| Attribute | Details |
|-----------|---------|
| **Coverage** | International commodity price indices (includes metals) |
| **Data Types** | Monthly indices, not absolute prices |
| **Latency** | Monthly/quarterly updates |
| **Price** | Free |
| **Format** | REST API, JSON/XML |
| **Auth** | API key (free registration) |
| **Limitation** | Index data only, not tradeable LME prices. Significantly delayed. |
| **URL** | https://ecos.bok.or.kr/api/ |

### Korean Securities Firms (NH선물, 삼성선물, etc.)

| Attribute | Details |
|-----------|---------|
| **Status** | No public APIs found for non-ferrous metals |
| **Note** | Korean futures companies provide LME data via their trading platforms (HTS/MTS) but do not offer public APIs for third-party consumption. Data is sourced from LME via licensed redistribution. |

---

## Category 5: LME Inventory (Warehouse Stocks) Data

| Source | Availability | Format | Cost |
|--------|-------------|--------|------|
| **LME Official** | Daily stocks report (14:30 London) | Website/PDF (no public API) | Free on website (delayed) |
| **Metals-API** | ST (Stock) data type | REST JSON | Included in subscription |
| **Bloomberg** | Full warehouse data by location | BLPAPI | Terminal license (~$24k/yr) |
| **Refinitiv/LSEG** | Full warehouse data by location | REST/WebSocket | Enterprise license |
| **Fastmarkets** | Included in data packages | API/Excel | Enterprise license |

---

## Summary Comparison Matrix

| API | All 6 Metals | Cash/3M | Real-time | Inventory | Free Tier | Python | Monthly Cost |
|-----|:---:|:---:|:---:|:---:|:---:|:---:|---:|
| **Metals-API** | Yes | Yes | ~60s | Yes (ST) | No | Yes | $20-$999 |
| **Commodities-API** | Yes | Partial | ~60s | No | No (trial) | No | $42-$4,117 |
| **MetalpriceAPI** | Partial | Unclear | Delayed | No | Yes (limited) | Yes | Free-?? |
| **Alpha Vantage** | No (Cu,Al only) | No | No (monthly) | No | Yes | Yes | Free-$50 |
| **Twelve Data** | Unclear | Unclear | ~1min | No | Yes (limited) | Yes | $79-$999 |
| **Yahoo/yfinance** | No (COMEX only) | No | 15-min delay | No | Yes | Yes | Free |
| **Refinitiv/LSEG** | Yes | Yes | Tick | Yes | No | Yes | ~$2,000+ |
| **Bloomberg** | Yes | Yes | Tick | Yes | No | Yes | ~$2,000+ |
| **Fastmarkets** | Yes | Yes | Near-RT | Yes | No | No | Enterprise |

---

## Recommendations

### Best Value for This Project (metal-bulletin)

1. **Metals-API** ($20-$100/month range) — Best balance of coverage, cost, and LME specificity
   - All 6 metals with Cash and 3M prices
   - 60-second update frequency
   - LME inventory data (ST type)
   - Python SDK available
   - Historical LME data from 2008

2. **Commodities-API** (higher cost) — Similar coverage, more expensive
   - Backup option if Metals-API quality is insufficient

3. **Alpha Vantage** (free) — For supplementary monthly benchmark data only
   - Only Cu and Al; monthly frequency; not LME-direct

### For Real-Time Trading Systems

- **Refinitiv/LSEG** or **Bloomberg** — if budget allows enterprise pricing
- These are the gold standard for institutional LME data

### Current Project Approach (PDF scraping from Metal Bulletin)

- The current approach of scraping Fastmarkets/Metal Bulletin PDFs provides official LME settlement prices at no API cost
- API alternatives would provide more granular intraday data but at monetary cost
- Metals-API is the most viable upgrade path for programmatic real-time data

---

## Source URLs

- https://metals-api.com / https://metals-api.com/documentation
- https://commodities-api.com / https://commodities-api.com/documentation
- https://metalpriceapi.com
- https://www.alphavantage.co/documentation/
- https://twelvedata.com/commodities
- https://finance.yahoo.com/quote/HG%3DF/
- https://www.fastmarkets.com/metals/
- https://www.lseg.com/en/data-analytics/financial-data/pricing-and-market-data
- https://www.worldbank.org/en/research/commodity-markets
- https://ecos.bok.or.kr/api/
- https://pypi.org/project/metals-api/
- https://github.com/metalpriceapi/metalpriceapi-python
