"""
Electricity Stops Service - Fetches and parses electricity outage announcements from ERM Zapad
"""
import asyncio
import aiohttp
import logging
import re
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import random

logger = logging.getLogger('walter.electricity_stops')


class ElectricityStopsService:
    """Service to fetch and parse electricity outage announcements from ERM Zapad"""

    def __init__(self):
        self.base_url = "https://info.ermzapad.bg/webint/vok/avplan.php"
        self.cache = None
        self.cache_time = None
        self.cache_duration = timedelta(minutes=30)

    async def get_electricity_stops(self) -> List[Dict]:
        """
        Fetch current electricity outage announcements

        Returns:
            List of outage dictionaries with location, type, start, end, region
        """
        # Check cache first
        if self.cache is not None and self.cache_time:
            if datetime.now() - self.cache_time < self.cache_duration:
                logger.info("Returning cached electricity stops")
                return self.cache

        try:
            async with aiohttp.ClientSession() as session:
                # Step 1: Fetch main page to get list of affected municipalities
                logger.info(f"Fetching electricity stops page: {self.base_url}")
                async with session.get(self.base_url) as response:
                    html = await response.text()

                # Step 2: Parse municipality IDs from HTML
                municipality_ids = self._parse_municipality_ids(html)
                logger.info(f"Found {len(municipality_ids)} affected municipalities")

                if not municipality_ids:
                    self.cache = []
                    self.cache_time = datetime.now()
                    return []

                # Step 3: Fetch details for each municipality
                stops = []
                for muni_id, muni_name, region in municipality_ids:
                    try:
                        muni_stops = await self._fetch_municipality_details(session, muni_id, muni_name, region)
                        stops.extend(muni_stops)
                    except Exception as e:
                        logger.error(f"Error fetching details for {muni_id}: {e}")
                        continue

                # Deduplicate stops based on location + start + end time
                unique_stops = []
                seen = set()
                for stop in stops:
                    key = (stop['location'], stop['start'], stop['end'], stop['category'])
                    if key not in seen:
                        seen.add(key)
                        unique_stops.append(stop)

                # Update cache
                self.cache = unique_stops
                self.cache_time = datetime.now()

                logger.info(f"Fetched {len(unique_stops)} unique electricity outage announcements (from {len(stops)} total)")
                return unique_stops

        except Exception as e:
            logger.error(f"Error fetching electricity stops: {e}", exc_info=True)
            return []

    def _parse_municipality_ids(self, html: str) -> List[tuple]:
        """
        Parse municipality IDs from the main page HTML

        Args:
            html: HTML content of the main page

        Returns:
            List of tuples (municipality_id, municipality_name, region_name)
        """
        municipalities = []
        soup = BeautifulSoup(html, 'html.parser')

        # Region mappings
        region_names = {
            'SOF': 'София-град',
            'SFO': 'Софийска област',
            'PER': 'Перник',
            'LOV': 'Ловеч',
            'VID': 'Видин',
            'KNL': 'Кюстендил',
            'BLG': 'Благоевград',
            'PVN': 'Плевен',
            'VRC': 'Враца',
            'MON': 'Монтана'
        }

        # Find all list items with onclick handlers for show_obstina
        # Only include Sofia-grad (SOF) municipalities
        for li in soup.find_all('li', onclick=True):
            onclick = li.get('onclick', '')
            # Pattern: show_obstina('SOF43','SOF')
            match = re.search(r"show_obstina\('([A-Z]+\d+)','([A-Z]+)'\)", onclick)
            if match:
                muni_id = match.group(1)
                region_code = match.group(2)

                # Filter: only Sofia-grad (SOF)
                if region_code != 'SOF':
                    continue

                region_name = region_names.get(region_code, region_code)

                # Extract municipality name from the li text
                muni_name = li.get_text(strip=True)
                # Clean up: remove icon text
                muni_name = re.sub(r'^община\s*', '', muni_name, flags=re.IGNORECASE)
                muni_name = muni_name.strip()

                municipalities.append((muni_id, muni_name, region_name))
                logger.debug(f"Found municipality: {muni_id} - {muni_name} ({region_name})")

        return municipalities

    async def _fetch_municipality_details(self, session: aiohttp.ClientSession,
                                           muni_id: str, muni_name: str,
                                           region: str) -> List[Dict]:
        """
        Fetch detailed outage data for a specific municipality

        Args:
            session: aiohttp session
            muni_id: Municipality ID (e.g., 'SOF43')
            muni_name: Municipality name
            region: Region name

        Returns:
            List of outage dictionaries
        """
        stops = []

        data = {
            'action': 'draw',
            'gm_obstina': muni_id,
            'lat': '0',
            'lon': '0'
        }

        async with session.post(self.base_url, data=data) as response:
            text = await response.text()

            # Handle UTF-8 BOM
            if text.startswith('\ufeff'):
                text = text[1:]

            if not text or text == '[]' or text == '{}':
                return stops

            try:
                import json
                result = json.loads(text)

                for key, outage in result.items():
                    if key == 'cnt' or not isinstance(outage, dict):
                        continue

                    # Determine if planned or unplanned
                    type_dist = outage.get('typedist', '').lower()
                    is_planned = 'планиран' in type_dist

                    stop = {
                        'location': outage.get('city_name') or outage.get('cities') or muni_name,
                        'municipality': muni_name,
                        'region': region,
                        'start': outage.get('begin_event', 'Не е указано'),
                        'end': outage.get('end_event', 'Не е указано'),
                        'category': 'planned' if is_planned else 'unplanned',
                        'type_bg': type_dist.capitalize() if type_dist else 'Неизвестно'
                    }
                    stops.append(stop)
                    logger.debug(f"Parsed outage: {stop['location']} ({stop['start']} - {stop['end']})")

            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error for {muni_id}: {e}")

        return stops

    def format_electricity_stops_message(self, stops: List[Dict]):
        """
        Format electricity stops into Discord messages with British humour
        Splits into multiple messages if needed (Discord 2000 char limit)

        Args:
            stops: List of electricity stop dictionaries

        Returns:
            Single message string or list of message strings if split needed
        """
        if not stops:
            return None

        # Separate planned and unplanned stops
        unplanned_stops = [s for s in stops if s.get('category') == 'unplanned']
        planned_stops = [s for s in stops if s.get('category') == 'planned']

        messages = []

        # British-style header
        header = "**Electricity Supply Interruptions**\n\n"
        header += "_ERM Zapad announces the following interruptions:_\n\n"

        # Unplanned stops section (emergencies first - more urgent)
        if unplanned_stops:
            current_msg = header + f"**CURRENT OUTAGES** ({len(unplanned_stops)})\n\n"

            for i, stop in enumerate(unplanned_stops, 1):
                location = stop.get('location', 'Location unspecified')[:80]
                municipality = stop.get('municipality', '')
                region = stop.get('region', '')
                start = stop.get('start', 'Time unspecified')
                end = stop.get('end', 'Time unspecified')

                # Compact format with region info
                loc_str = f"{location}"
                if municipality and municipality.upper() not in location.upper():
                    loc_str += f", {municipality}"
                if region:
                    loc_str += f" ({region})"

                current_msg += f"**{i}.** {loc_str}\n"
                current_msg += f"   {start} - {end}\n\n"

            # Check if message is too long
            if len(current_msg) > 1900:
                chunk_msg = header + f"**CURRENT OUTAGES** (Part 1)\n\n"
                for i, stop in enumerate(unplanned_stops, 1):
                    location = stop.get('location', 'Location unspecified')[:80]
                    start = stop.get('start', 'Time unspecified')
                    end = stop.get('end', 'Time unspecified')

                    entry = f"**{i}.** {location}\n   {start} - {end}\n\n"

                    if len(chunk_msg) + len(entry) > 1900:
                        messages.append(chunk_msg)
                        chunk_msg = f"**CURRENT OUTAGES** (Part {len(messages) + 1})\n\n"

                    chunk_msg += entry

                if chunk_msg:
                    messages.append(chunk_msg)
            else:
                messages.append(current_msg)

        # Planned stops section
        if planned_stops:
            planned_msg = f"**PLANNED MAINTENANCE** ({len(planned_stops)})\n\n"

            for i, stop in enumerate(planned_stops, 1):
                location = stop.get('location', 'Location unspecified')[:80]
                municipality = stop.get('municipality', '')
                region = stop.get('region', '')
                start = stop.get('start', 'Time unspecified')
                end = stop.get('end', 'Time unspecified')

                loc_str = f"{location}"
                if municipality and municipality.upper() not in location.upper():
                    loc_str += f", {municipality}"
                if region:
                    loc_str += f" ({region})"

                planned_msg += f"**{i}.** {loc_str}\n"
                planned_msg += f"   {start} - {end}\n\n"

            # Check length
            if len(planned_msg) > 1900:
                chunk_msg = f"**PLANNED MAINTENANCE** (Part 1)\n\n"
                for i, stop in enumerate(planned_stops, 1):
                    location = stop.get('location', 'Location unspecified')[:80]
                    start = stop.get('start', 'Time unspecified')
                    end = stop.get('end', 'Time unspecified')

                    entry = f"**{i}.** {location}\n   {start} - {end}\n\n"

                    if len(chunk_msg) + len(entry) > 1900:
                        messages.append(chunk_msg)
                        part_num = len([m for m in messages if 'PLANNED' in m]) + 1
                        chunk_msg = f"**PLANNED MAINTENANCE** (Part {part_num})\n\n"

                    chunk_msg += entry

                if chunk_msg:
                    messages.append(chunk_msg)
            else:
                messages.append(planned_msg)

        # Add footer to last message
        if messages:
            footers = [
                "\n_Do charge your devices beforehand._",
                "\n_The Victorians managed with gas lamps._",
                "\n_Modern inconvenience, as scheduled._",
                "\n_Best locate the candles._"
            ]
            messages[-1] += random.choice(footers)

        return messages if len(messages) > 1 else messages[0] if messages else None

    def format_no_stops_message(self) -> str:
        """Return a cheerful message when there are no electricity stops"""
        messages = [
            "**Splendid News!**\n\n_No electricity interruptions scheduled at present. The grid hums along reliably. One can enjoy modern conveniences without strategic candlestick placement._",
            "**All Clear!**\n\n_I'm delighted to report that ERM Zapad is behaving itself today. No interruptions to the electricity supply. Your devices may charge in peace._",
            "**Power Status: Flowing Magnificently**\n\n_Not a single planned interruption in sight. The electrons are performing their duty admirably. How refreshingly civilised._",
            "**Excellent News!**\n\n_The electrical works are in fine fettle today. No outages to report. One might even dare to schedule an extended gaming session._"
        ]

        return random.choice(messages)
