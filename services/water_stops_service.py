"""
Water Stops Service - Fetches and parses water stop announcements from Sofia Water
"""
import asyncio
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import random

logger = logging.getLogger('walter.water_stops')


class WaterStopsService:
    """Service to fetch and parse water stop announcements from Sofia Water"""

    def __init__(self):
        # The actual content is in an iframe
        self.url = "https://gispx.sofiyskavoda.bg/WebApp.InfoCenter/?a=0&tab=0"
        self.cache = None
        self.cache_time = None
        self.cache_duration = timedelta(minutes=30)  # Cache for 30 minutes

    async def get_water_stops(self) -> List[Dict]:
        """
        Fetch current water stop announcements using Playwright

        Returns:
            List of water stop dictionaries with location, type, description, start, end
        """
        # Check cache first
        if self.cache and self.cache_time:
            if datetime.now() - self.cache_time < self.cache_duration:
                logger.info("Returning cached water stops")
                return self.cache

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()

                logger.info(f"Loading water stops page: {self.url}")

                # Load the page
                await page.goto(self.url, wait_until='load', timeout=30000)

                # Wait for JavaScript to render the content and splash screen to disappear
                logger.info("Waiting for content to render...")
                await page.wait_for_timeout(3000)

                # Wait for splash screen to disappear
                try:
                    await page.wait_for_selector('div#divSplashScreenContainer', state='hidden', timeout=10000)
                    logger.info("Splash screen hidden")
                except Exception as e:
                    logger.warning(f"Splash screen wait timeout: {e}")

                # Expand accordion sections to get all content using JavaScript
                logger.info("Expanding accordion sections...")

                # Use JavaScript to click and expand the sanitaryBackup section
                try:
                    await page.evaluate("""
                        // Find and click the accordion to expand planned stops
                        const accordion = document.getElementById('divAccordianImagesanitaryBackup');
                        if (accordion) {
                            accordion.click();
                        }
                    """)
                    await page.wait_for_timeout(2000)
                    logger.info("Expanded Планирани спирания section via JavaScript")
                except Exception as e:
                    logger.warning(f"Could not expand sanitaryBackup accordion: {e}")

                # Wait a bit more for content to load after expanding
                await page.wait_for_timeout(2000)

                # Get the fully rendered HTML
                html = await page.content()
                await browser.close()

                # Parse the HTML
                stops = self._parse_water_stops(html)

                # Update cache
                self.cache = stops
                self.cache_time = datetime.now()

                logger.info(f"Fetched {len(stops)} water stop announcements")
                return stops

        except Exception as e:
            logger.error(f"Error fetching water stops: {e}", exc_info=True)
            return []

    def _parse_water_stops(self, html: str) -> List[Dict]:
        """
        Parse water stop announcements from rendered HTML

        Args:
            html: Fully rendered HTML from Playwright

        Returns:
            List of parsed water stop dictionaries
        """
        stops = []
        soup = BeautifulSoup(html, 'lxml')

        logger.info(f"Parsing HTML (length: {len(html)})")

        # Parse both current stops (infrastructureAlerts) and planned stops (sanitaryBackup)
        sections = [
            {
                'id': 'infrastructureAlertsContent',
                'name': 'Current Stops',
                'category': 'current'
            },
            {
                'id': 'sanitaryBackupContent',
                'name': 'Planned Stops',
                'category': 'planned'
            }
        ]

        for section in sections:
            section_div = soup.find('div', id=section['id'])

            if not section_div:
                logger.warning(f"Could not find section: {section['id']}")
                continue

            # Find the table with water stops in this section
            table = section_div.find('table', class_='tableWaterStopInfo')

            if not table:
                logger.info(f"No table found in {section['name']}")
                continue

            # Find all rows with water stop data
            rows = table.find_all('tr', class_='trRowDefault')
            logger.info(f"Found {len(rows)} rows in {section['name']}")

            for row in rows:
                try:
                    cell = row.find('td')
                    if not cell:
                        continue

                    # Get text with newlines preserved
                    text = cell.get_text(separator='\n', strip=True)

                    # Extract fields using Bulgarian keywords
                    location = self._extract_field(text, 'Местоположение:')
                    stop_type = self._extract_field(text, 'Тип:')
                    description = self._extract_field(text, 'Описание:')
                    start_time = self._extract_field(text, 'Начало:')
                    end_time = self._extract_field(text, 'Край:')

                    if location or start_time or end_time:
                        stop = {
                            'location': location or 'Location not specified',
                            'type': stop_type or 'Unknown',
                            'description': description or '',
                            'start': start_time or 'Time not specified',
                            'end': end_time or 'Time not specified',
                            'category': section['category']
                        }
                        stops.append(stop)
                        logger.info(f"Parsed [{section['category']}]: {location} ({start_time} - {end_time})")

                except Exception as e:
                    logger.error(f"Error parsing water stop row: {e}")
                    continue

        return stops

    def _extract_field(self, text: str, field_name: str) -> Optional[str]:
        """
        Extract a specific field value from text

        Args:
            text: The text to search in
            field_name: The field name to look for (e.g., 'Местоположение:')

        Returns:
            The extracted field value or None
        """
        try:
            if field_name not in text:
                return None

            # Split by field name and get the part after it
            parts = text.split(field_name, 1)
            if len(parts) < 2:
                return None

            # Get everything until the next field marker or newline
            remaining = parts[1]

            # Find the next field (starts with capital letter followed by colon)
            # Bulgarian field markers: Местоположение:, Тип:, Описание:, Начало:, Край:
            field_markers = ['Тип:', 'Описание:', 'Начало:', 'Край:']

            # Find the nearest field marker
            next_marker_pos = len(remaining)
            for marker in field_markers:
                pos = remaining.find(marker)
                if pos != -1 and pos < next_marker_pos:
                    next_marker_pos = pos

            # Extract the value
            field_value = remaining[:next_marker_pos].strip()

            return field_value if field_value else None

        except Exception as e:
            logger.error(f"Error extracting field {field_name}: {e}")
            return None

    def format_water_stops_message(self, stops: List[Dict]):
        """
        Format water stops into Discord messages with British humour
        Splits into multiple messages if needed (Discord 2000 char limit)

        Args:
            stops: List of water stop dictionaries

        Returns:
            Single message string or list of message strings if split needed
        """
        if not stops:
            return None

        # Separate current and planned stops
        current_stops = [s for s in stops if s.get('category') == 'current']
        planned_stops = [s for s in stops if s.get('category') == 'planned']

        messages = []

        # British-style header
        header = "💧 **Water Supply Interruptions**\n\n"
        header += "_Sofia Water announces the following interruptions:_\n\n"

        # Current stops section
        if current_stops:
            current_msg = header + f"⚡ **CURRENT STOPS** ({len(current_stops)})\n\n"

            for i, stop in enumerate(current_stops, 1):
                location = stop.get('location', 'Location unspecified')[:100]  # Truncate long locations
                start = stop.get('start', 'Time unspecified')
                end = stop.get('end', 'Time unspecified')

                # Compact format
                current_msg += f"**{i}.** {location}\n"
                current_msg += f"   ⏰ {start} → {end}\n\n"

            # Check if message is too long, split if needed
            if len(current_msg) > 1900:
                # Split current stops into chunks
                chunk_msg = header + f"⚡ **CURRENT STOPS** (Part 1)\n\n"
                for i, stop in enumerate(current_stops, 1):
                    location = stop.get('location', 'Location unspecified')[:100]
                    start = stop.get('start', 'Time unspecified')
                    end = stop.get('end', 'Time unspecified')

                    entry = f"**{i}.** {location}\n   ⏰ {start} → {end}\n\n"

                    if len(chunk_msg) + len(entry) > 1900:
                        messages.append(chunk_msg)
                        chunk_msg = f"⚡ **CURRENT STOPS** (Part {len(messages) + 1})\n\n"

                    chunk_msg += entry

                if chunk_msg:
                    messages.append(chunk_msg)
            else:
                messages.append(current_msg)

        # Planned stops section
        if planned_stops:
            planned_msg = f"📋 **PLANNED STOPS** ({len(planned_stops)})\n\n"

            for i, stop in enumerate(planned_stops, 1):
                location = stop.get('location', 'Location unspecified')[:100]
                start = stop.get('start', 'Time unspecified')
                end = stop.get('end', 'Time unspecified')

                planned_msg += f"**{i}.** {location}\n"
                planned_msg += f"   📅 {start} → {end}\n\n"

            # Check length
            if len(planned_msg) > 1900:
                # Split if too long
                chunk_msg = f"📋 **PLANNED STOPS** (Part 1)\n\n"
                for i, stop in enumerate(planned_stops, 1):
                    location = stop.get('location', 'Location unspecified')[:100]
                    start = stop.get('start', 'Time unspecified')
                    end = stop.get('end', 'Time unspecified')

                    entry = f"**{i}.** {location}\n   📅 {start} → {end}\n\n"

                    if len(chunk_msg) + len(entry) > 1900:
                        messages.append(chunk_msg)
                        chunk_msg = f"📋 **PLANNED STOPS** (Part {len(messages) - len([m for m in messages if 'CURRENT' in m]) + 1})\n\n"

                    chunk_msg += entry

                if chunk_msg:
                    messages.append(chunk_msg)
            else:
                messages.append(planned_msg)

        # Add footer to last message
        if messages:
            footers = [
                "\n_Do fill your kettle beforehand._",
                "\n_The Victorians managed with pumps._",
                "\n_Municipal inconvenience, as scheduled._",
                "\n_Mustn't grumble._"
            ]
            messages[-1] += random.choice(footers)

        return messages if len(messages) > 1 else messages[0] if messages else None

    def format_no_stops_message(self) -> str:
        """Return a cheerful message when there are no water stops"""
        messages = [
            "💧 **Jolly Good News!** 🎉\n\n_No water stoppages scheduled at present. The taps remain reliably operational, as nature intended. One can make tea without strategic planning for once._",
            "💧 **All Clear!** ✨\n\n_I'm delighted to report that Sofia Water is behaving itself today. No interruptions to the water supply. Carry on with your ablutions without concern._",
            "💧 **Water Status: Flowing Splendidly** 🚰\n\n_Not a single planned interruption in sight. The pipes are performing their duty admirably. How refreshingly civilised._",
            "💧 **Excellent News!** 🎊\n\n_The waterworks are in fine fettle today. No stoppages to report. One might even dare to schedule a lengthy bath without military-grade planning._"
        ]

        return random.choice(messages)
