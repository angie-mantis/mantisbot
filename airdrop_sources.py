"""
MantisTrackerBot — Airdrop Data Sources
Multi-source scraper + curated fallback database
"""

import re
import hashlib
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
}

PRIORITY_CHAINS = ["SOL", "BTC", "ETH", "BNB"]


def make_id(name: str, url: str = "") -> str:
    return hashlib.md5(f"{name}{url}".encode()).hexdigest()[:12]


def detect_chain(text: str) -> str:
    mapping = {
        "SOLANA": "SOL", "SOL ": "SOL",
        "BITCOIN": "BTC", " BTC": "BTC",
        "ETHEREUM": "ETH", " ETH": "ETH",
        "BINANCE": "BNB", " BNB": "BNB", "BSC": "BNB",
        "BASE": "BASE",
        "ARBITRUM": "ARB", " ARB": "ARB",
        "POLYGON": "MATIC", "MATIC": "MATIC",
        "AVALANCHE": "AVAX", "AVAX": "AVAX",
        "APTOS": "APT",
        "SUI ": "SUI",
        "TON ": "TON",
        "NEAR": "NEAR",
        "COSMOS": "ATOM",
    }
    text_up = " " + text.upper() + " "
    for keyword, chain in mapping.items():
        if keyword in text_up:
            return chain
    return "OTHER"


# ─── SCRAPERS ─────────────────────────────────────────────────────────────────

def scrape_airdrops_io() -> list[dict]:
    """Scrape airdrops.io — tries multiple page selectors."""
    airdrops = []
    urls = [
        "https://airdrops.io/latest/",
        "https://airdrops.io/",
        "https://airdrops.io/specials/",
    ]
    for url in urls:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=18)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")

            # Strategy 1: article tags
            cards = soup.find_all("article")
            # Strategy 2: divs with airdrop classes
            if not cards:
                cards = soup.find_all("div", class_=re.compile(r"airdrop|listing|card", re.I))
            # Strategy 3: any li inside an airdrop list
            if not cards:
                cards = soup.find_all("li", class_=re.compile(r"airdrop|item", re.I))

            for card in cards[:25]:
                try:
                    name_el = card.find(["h2", "h3", "h4", "strong"])
                    name = name_el.get_text(strip=True) if name_el else ""
                    if not name or len(name) < 2:
                        continue
                    link_el = card.find("a", href=True)
                    link = link_el["href"] if link_el else ""
                    if link and not link.startswith("http"):
                        link = "https://airdrops.io" + link
                    desc_el = card.find("p")
                    desc = desc_el.get_text(strip=True)[:200] if desc_el else ""
                    card_text = card.get_text(" ", strip=True)
                    chain = detect_chain(card_text + " " + name)
                    airdrops.append({
                        "id": make_id(name, link),
                        "name": name,
                        "description": desc,
                        "chain": chain,
                        "url": link,
                        "requirements": card_text[:300],
                        "source": "airdrops.io",
                        "status": "active",
                        "scraped_at": datetime.now().isoformat(),
                    })
                except Exception:
                    continue

            if airdrops:
                logger.info(f"airdrops.io ({url}): {len(airdrops)} found")
                break
        except Exception as e:
            logger.warning(f"airdrops.io scrape error ({url}): {e}")
    return airdrops


def scrape_coinmarketcap() -> list[dict]:
    """Scrape CoinMarketCap airdrop page."""
    airdrops = []
    try:
        resp = requests.get("https://coinmarketcap.com/airdrop/", headers=HEADERS, timeout=18)
        if resp.status_code != 200:
            return airdrops
        soup = BeautifulSoup(resp.text, "html.parser")

        # CMC renders client-side; try to grab static content
        rows = soup.find_all("tr")
        for row in rows[1:25]:
            try:
                cells = row.find_all("td")
                if len(cells) < 2:
                    continue
                name = cells[0].get_text(strip=True)
                if not name or len(name) < 2:
                    continue
                link_el = row.find("a", href=True)
                link = link_el["href"] if link_el else ""
                if link and not link.startswith("http"):
                    link = "https://coinmarketcap.com" + link
                row_text = row.get_text(" ", strip=True)
                chain = detect_chain(row_text + " " + name)
                airdrops.append({
                    "id": make_id(name, link),
                    "name": name,
                    "description": row_text[:200],
                    "chain": chain,
                    "url": link,
                    "requirements": row_text[:300],
                    "source": "coinmarketcap",
                    "status": "active",
                    "scraped_at": datetime.now().isoformat(),
                })
            except Exception:
                continue
        logger.info(f"CoinMarketCap: {len(airdrops)} found")
    except Exception as e:
        logger.warning(f"CMC scrape error: {e}")
    return airdrops


def scrape_dappradar() -> list[dict]:
    """Scrape DappRadar airdrops."""
    airdrops = []
    try:
        resp = requests.get("https://dappradar.com/airdrops", headers=HEADERS, timeout=18)
        if resp.status_code != 200:
            return airdrops
        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.find_all(["div", "article"], class_=re.compile(r"airdrop|card|item", re.I))
        for card in cards[:20]:
            try:
                name_el = card.find(["h2", "h3", "h4", "span", "p"])
                name = name_el.get_text(strip=True) if name_el else ""
                if not name or len(name) < 2:
                    continue
                link_el = card.find("a", href=True)
                link = link_el["href"] if link_el else ""
                if link and not link.startswith("http"):
                    link = "https://dappradar.com" + link
                card_text = card.get_text(" ", strip=True)
                chain = detect_chain(card_text + " " + name)
                airdrops.append({
                    "id": make_id(name, link),
                    "name": name,
                    "description": card_text[:200],
                    "chain": chain,
                    "url": link,
                    "requirements": card_text[:300],
                    "source": "dappradar",
                    "status": "active",
                    "scraped_at": datetime.now().isoformat(),
                })
            except Exception:
                continue
        logger.info(f"DappRadar: {len(airdrops)} found")
    except Exception as e:
        logger.warning(f"DappRadar scrape error: {e}")
    return airdrops


# ─── CURATED DATABASE ─────────────────────────────────────────────────────────
# High-confidence, researched airdrops — updated manually alongside code
# Status: potential | confirmed | active | snapshot | ended

CURATED_AIRDROPS = [
    # ── SOLANA ──
    {
        "id": "cur_sol_001",
        "name": "Backpack Exchange",
        "description": "Solana-based exchange and wallet by Mad Lads team. Active traders and xNFT holders expected to qualify.",
        "chain": "SOL",
        "url": "https://backpack.exchange",
        "requirements": "Create account, trade on exchange, hold Mad Lads xNFT, refer friends",
        "source": "curated",
        "status": "potential",
        "est_value": "$200–$2,000",
        "deadline": "TBA",
    },
    {
        "id": "cur_sol_002",
        "name": "Drift Protocol",
        "description": "Solana perpetuals DEX. DRIFT token already launched; retroactive rewards for early users ongoing.",
        "chain": "SOL",
        "url": "https://drift.trade",
        "requirements": "Trade perpetuals, provide liquidity, stake DRIFT token",
        "source": "curated",
        "status": "active",
        "est_value": "$50–$500",
        "deadline": "Ongoing",
    },
    {
        "id": "cur_sol_003",
        "name": "Kamino Finance",
        "description": "Solana DeFi yield optimizer. KMNO token airdrop for liquidity providers and borrowers.",
        "chain": "SOL",
        "url": "https://kamino.finance",
        "requirements": "Provide liquidity, borrow assets, hold SOL positions on Kamino",
        "source": "curated",
        "status": "active",
        "est_value": "$100–$1,000",
        "deadline": "Ongoing seasons",
    },
    {
        "id": "cur_sol_004",
        "name": "Sanctum (LST Wars)",
        "description": "Solana liquid staking aggregator. INF token holders and LST liquidity providers qualify.",
        "chain": "SOL",
        "url": "https://sanctum.so",
        "requirements": "Hold LST tokens, provide liquidity to Sanctum pools, stake SOL via Sanctum",
        "source": "curated",
        "status": "active",
        "est_value": "$50–$800",
        "deadline": "Ongoing",
    },
    {
        "id": "cur_sol_005",
        "name": "Tensor NFT Marketplace",
        "description": "Solana's leading NFT marketplace. TNSR token launched; ongoing trading rewards program.",
        "chain": "SOL",
        "url": "https://tensor.trade",
        "requirements": "Trade NFTs on Tensor, stake TNSR, use Tensorian NFT for boosts",
        "source": "curated",
        "status": "active",
        "est_value": "$30–$300",
        "deadline": "Ongoing",
    },
    # ── ETHEREUM ──
    {
        "id": "cur_eth_001",
        "name": "MetaMask Token (MASK)",
        "description": "MetaMask wallet has long been rumored to launch a governance token. Most-used Ethereum wallet globally.",
        "chain": "ETH",
        "url": "https://metamask.io",
        "requirements": "Use MetaMask wallet regularly, swap via MetaMask, bridge assets, use MetaMask Snaps",
        "source": "curated",
        "status": "potential",
        "est_value": "$500–$5,000",
        "deadline": "Unannounced",
    },
    {
        "id": "cur_eth_002",
        "name": "Monad Testnet",
        "description": "High-performance EVM-compatible L1 blockchain. Testnet live; mainnet airdrop highly anticipated.",
        "chain": "ETH",
        "url": "https://monad.xyz",
        "requirements": "Use Monad testnet, complete transactions, interact with DApps, join Discord",
        "source": "curated",
        "status": "potential",
        "est_value": "$200–$3,000",
        "deadline": "Pre-mainnet",
    },
    {
        "id": "cur_eth_003",
        "name": "Scroll zkEVM",
        "description": "zkEVM Layer 2 on Ethereum. Active on mainnet; SCR token launched with ongoing marks program.",
        "chain": "ETH",
        "url": "https://scroll.io",
        "requirements": "Bridge ETH to Scroll, use Scroll DApps, provide liquidity, hold Scroll NFTs",
        "source": "curated",
        "status": "active",
        "est_value": "$50–$500",
        "deadline": "Ongoing seasons",
    },
    {
        "id": "cur_eth_004",
        "name": "EigenLayer Restaking",
        "description": "Ethereum restaking protocol. EIGEN token live; restakers earn additional AVS rewards.",
        "chain": "ETH",
        "url": "https://eigenlayer.xyz",
        "requirements": "Restake ETH or LSTs on EigenLayer, hold stakedETH positions, run an AVS operator",
        "source": "curated",
        "status": "active",
        "est_value": "$100–$2,000",
        "deadline": "Ongoing",
    },
    {
        "id": "cur_eth_005",
        "name": "Pendle Finance",
        "description": "Yield tokenization protocol on Ethereum and multiple L2s. Growing ecosystem incentives.",
        "chain": "ETH",
        "url": "https://pendle.finance",
        "requirements": "Provide liquidity, hold vePENDLE, trade yield tokens, participate in governance",
        "source": "curated",
        "status": "active",
        "est_value": "$50–$1,000",
        "deadline": "Ongoing",
    },
    # ── BNB ──
    {
        "id": "cur_bnb_001",
        "name": "Binance Web3 Wallet Airdrop",
        "description": "Binance's Web3 Wallet offers MegaDrop campaigns — stake BNB or complete Web3 tasks to earn.",
        "chain": "BNB",
        "url": "https://www.binance.com/en/web3wallet",
        "requirements": "Lock BNB in Simple Earn, complete Web3 quests via Binance Web3 Wallet",
        "source": "curated",
        "status": "active",
        "est_value": "$20–$500",
        "deadline": "Rotating campaigns",
    },
    {
        "id": "cur_bnb_002",
        "name": "Venus Protocol",
        "description": "BNB Chain lending/borrowing protocol. XVS token rewards for suppliers and borrowers.",
        "chain": "BNB",
        "url": "https://venus.io",
        "requirements": "Supply assets, borrow on Venus, stake XVS in vault",
        "source": "curated",
        "status": "active",
        "est_value": "$20–$200",
        "deadline": "Ongoing",
    },
    {
        "id": "cur_bnb_003",
        "name": "Lista DAO (LISTA)",
        "description": "BNB Chain liquid staking and stablecoin protocol. Ongoing rewards for stakers and lisUSD users.",
        "chain": "BNB",
        "url": "https://lista.org",
        "requirements": "Stake BNB for slisBNB, mint lisUSD, provide liquidity on PancakeSwap",
        "source": "curated",
        "status": "active",
        "est_value": "$30–$400",
        "deadline": "Ongoing",
    },
    # ── BITCOIN ECOSYSTEM ──
    {
        "id": "cur_btc_001",
        "name": "Babylon Bitcoin Staking",
        "description": "Native Bitcoin staking protocol securing PoS chains. BABY token airdrop for BTC stakers.",
        "chain": "BTC",
        "url": "https://babylonlabs.io",
        "requirements": "Stake native BTC via Babylon (no bridge required), hold stBTC positions",
        "source": "curated",
        "status": "confirmed",
        "est_value": "$100–$2,000",
        "deadline": "Mainnet imminent",
    },
    {
        "id": "cur_btc_002",
        "name": "Merlin Chain BTC L2",
        "description": "Bitcoin Layer 2 with EVM compatibility. MERL token launched; ongoing DeFi incentives.",
        "chain": "BTC",
        "url": "https://merlinchain.io",
        "requirements": "Bridge BTC to Merlin, use Merlin DApps, provide liquidity, stake MERL",
        "source": "curated",
        "status": "active",
        "est_value": "$30–$300",
        "deadline": "Ongoing",
    },
    {
        "id": "cur_btc_003",
        "name": "Stacks (STX) sBTC Launch",
        "description": "Bitcoin smart contract layer. sBTC (1:1 BTC-backed) launch brings new airdrop opportunities for Stackers.",
        "chain": "BTC",
        "url": "https://stacks.co",
        "requirements": "Stack STX to earn BTC yield, use sBTC in DeFi, hold Stacks NFTs",
        "source": "curated",
        "status": "active",
        "est_value": "$50–$500",
        "deadline": "Ongoing",
    },
    # ── MULTI-CHAIN / OTHER HIGH VALUE ──
    {
        "id": "cur_multi_001",
        "name": "Hyperliquid (HYPE)",
        "description": "High-performance perp DEX on its own L1. HYPE token already distributed; trading rewards ongoing.",
        "chain": "ETH",
        "url": "https://hyperliquid.xyz",
        "requirements": "Trade perpetuals on Hyperliquid, provide liquidity, stake HYPE",
        "source": "curated",
        "status": "active",
        "est_value": "$50–$2,000",
        "deadline": "Ongoing",
    },
    {
        "id": "cur_multi_002",
        "name": "Berachain (BERA)",
        "description": "EVM L1 with Proof of Liquidity consensus. BERA/BGT token. Active mainnet with high TVL incentives.",
        "chain": "ETH",
        "url": "https://berachain.com",
        "requirements": "Provide liquidity on Berachain DEX, hold BGT gauge votes, use Honey stablecoin",
        "source": "curated",
        "status": "active",
        "est_value": "$100–$1,500",
        "deadline": "Ongoing seasons",
    },
]


def get_curated_airdrops() -> list[dict]:
    """Return curated list with scraped_at timestamp added."""
    now = datetime.now().isoformat()
    result = []
    for a in CURATED_AIRDROPS:
        entry = dict(a)
        entry["scraped_at"] = now
        result.append(entry)
    return result


def fetch_all_airdrops() -> list[dict]:
    """
    Master fetch: runs all scrapers, deduplicates,
    supplements with curated DB, sorts by priority chain.
    """
    logger.info("🔄 Fetching airdrops from all sources...")
    all_airdrops = []

    # Live scrapers
    for scraper_fn, label in [
        (scrape_airdrops_io, "airdrops.io"),
        (scrape_coinmarketcap, "CoinMarketCap"),
        (scrape_dappradar, "DappRadar"),
    ]:
        try:
            results = scraper_fn()
            logger.info(f"  {label}: {len(results)} found")
            all_airdrops.extend(results)
        except Exception as e:
            logger.warning(f"  {label} failed: {e}")

    # Deduplicate
    seen = set()
    unique = []
    for a in all_airdrops:
        if a["id"] not in seen:
            seen.add(a["id"])
            unique.append(a)

    # Always add curated entries (they fill gaps + provide fallback)
    for a in get_curated_airdrops():
        if a["id"] not in seen:
            seen.add(a["id"])
            unique.append(a)

    # Sort: priority chains first, then by name
    def sort_key(a):
        chain = a.get("chain", "OTHER")
        priority = PRIORITY_CHAINS.index(chain) if chain in PRIORITY_CHAINS else 99
        return (priority, a.get("name", ""))

    unique.sort(key=sort_key)
    logger.info(f"✅ Total unique airdrops: {len(unique)}")
    return unique
