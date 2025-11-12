import openai
import os
import asyncio
import random
import time
import logging
from typing import Dict, Optional

logger = logging.getLogger('walter.ai_service')

class AIService:
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        openai.api_key = self.api_key
        self.client = openai.OpenAI(api_key=self.api_key)
        
    async def generate_victorian_commentary(self, events) -> str:
        """Generate Victorian-style commentary for historical events"""

        # Handle both single event (Dict) and multiple events (List[Dict])
        if isinstance(events, dict):
            events = [events]

        # Select a prompt style (rotate for variety)
        prompt_style = random.choice(['standard', 'pooter', 'jerome'])

        prompt = self._build_prompt(events, prompt_style)

        # Retry logic with exponential backoff
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await self._call_openai(prompt)

                # Format the response
                formatted_response = self._format_response(response, events)
                return formatted_response

            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Failed to generate content after {max_retries} attempts: {e}")
                    # Return fallback content
                    return self._generate_fallback(events)

                wait_time = (2 ** attempt) + random.uniform(0, 1)
                logger.warning(f"API call failed (attempt {attempt + 1}), retrying in {wait_time:.2f}s")
                await asyncio.sleep(wait_time)

        return self._generate_fallback(events)
    
    def _build_prompt(self, events: list, style: str) -> str:
        """Build the prompt based on the selected style"""

        # Build events list for the prompt
        events_text = ""
        for i, event in enumerate(events, 1):
            year = event.get('year', 'unknown year')
            description = event.get('description', 'An event occurred')
            events_text += f"{i}. In {year}, {description}\n"

        if style == 'pooter':
            return f"""You are Charles Pooter from "Diary of a Nobody," recording notable historical events with characteristic earnestness and blind spots.

Historical events for today:
{events_text}

Write a diary entry covering these events (200-300 words total):

First paragraph: Introduce today's historical observations with characteristic Pooter earnestness
Second-to-fourth paragraphs: Comment on each event briefly with:
- Slight misunderstandings of their importance
- Comparisons to mundane personal matters
- Mild concerns about propriety
Final paragraph: Digress into a domestic matter that seems equally important to world history

Style: Formal Victorian language, unintentionally comic, self-important about trivia

Begin: "📜 **On This Day in History**

I observe with interest that several momentous events occurred on this date..."
"""
        
        elif style == 'jerome':
            return f"""You are writing in the style of Jerome K. Jerome from "Three Men in a Boat" - observational, meandering, self-deprecating.

Historical events for today:
{events_text}

Requirements:
- Open with "📜 **On This Day in History**"
- Present each historical fact briefly (1-2 sentences each)
- Between events, add humorous digressions and tangential observations
- Include self-deprecating observations about modern life
- End with an understated, meandering conclusion

Style: Conversational, dry wit, tendency to ramble
Length: 250-350 words
Voice: Educated but unpretentious, gently mocking

CRITICAL: Base your entry ONLY on these verified historical facts. Do NOT add invented historical details."""
        
        else:  # standard
            return f"""You are creating daily "On This Day in History" content for a Discord server. Your style combines Victorian British humor (Jerome K. Jerome and George Grossmith) with modern Discord formatting.

Historical events for today:
{events_text}

Requirements:
- Open with "📜 **On This Day in History**"
- Present each historical fact (1-2 sentences each)
- After each fact, add brief Victorian-style commentary
- Include several of these elements throughout:
  * Self-deprecating comparisons to modern times
  * Mundane digressions
  * Faux-outrage at historical figures' behavior
  * Terrible Victorian puns

Style: Dry, understated, conversational but with Victorian sensibility
Tone: Gently mocking, observational, deadpan
Length: 300-400 words total (Discord-friendly)
Voice: Educated but not stuffy, witty but not try-hard

Avoid:
- Modern slang or memes
- Excessive exclamation marks
- Obvious jokes or sarcasm markers

CRITICAL: Base your entry ONLY on these verified historical facts.
Do NOT add invented historical details. Your creativity should be in the COMMENTARY and STYLE, not in fabricating additional historical information."""
    
    async def _call_openai(self, prompt: str) -> str:
        """Make the actual API call to OpenAI"""
        
        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        
        def api_call():
            return self.client.chat.completions.create(
                model="gpt-4o",  # Using GPT-4o for best cost/performance
                messages=[
                    {
                        "role": "system",
                        "content": "You are a Victorian humorist writing daily historical commentary with dry wit and understatement."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=600,  # Increased for multiple events
                temperature=0.8  # Some creativity but not too wild
            )
        
        response = await loop.run_in_executor(None, api_call)
        return response.choices[0].message.content
    
    def _format_response(self, response: str, events: list) -> str:
        """Ensure the response is properly formatted for Discord"""

        # Add @here mention at the start
        formatted = f"@here {response}"

        # Ensure it's not too long for Discord (2000 char limit)
        if len(formatted) > 1900:
            # Find the last complete sentence before 1850 chars
            truncate_point = 1850
            text_to_truncate = formatted[:truncate_point]

            # Try to find last sentence ending (. ! ?)
            last_sentence = max(
                text_to_truncate.rfind('. '),
                text_to_truncate.rfind('! '),
                text_to_truncate.rfind('? ')
            )

            if last_sentence > 1500:  # Found a reasonable sentence boundary
                formatted = formatted[:last_sentence + 1]
            else:
                # Fall back to word boundary
                last_space = text_to_truncate.rfind(' ')
                if last_space > 1500:
                    formatted = formatted[:last_space]
                else:
                    # Hard truncate as last resort
                    formatted = formatted[:1850]

            # Add note about truncation
            formatted += "\n\n_[Commentary continues, but Discord message limit reached. History repeats itself, as does character truncation.]_"

        return formatted
    
    def _generate_fallback(self, events) -> str:
        """Generate fallback content if AI fails"""

        # Handle both single event and list of events
        if isinstance(events, dict):
            events = [events]

        # Build event list
        events_text = "📜 **On This Day in History**\n\n"

        for event in events[:5]:  # Limit to 5 events
            year = event.get('year', 'unknown year')
            description = event.get('description', 'Something interesting happened')
            events_text += f"**{year}:** {description}\n\n"

        # Add a Victorian-style closing remark
        closing_remarks = [
            "One rather suspects our ancestors had altogether too much time on their hands. Though I suppose we can hardly talk, what with spending our days staring at glowing rectangles and arguing with strangers about trivialities.",

            "Remarkable how history repeats itself, though with progressively worse fashion sense each time around. I dare say future generations will look back upon our era with equal bemusement.",

            "I mentioned these events to Carrie at breakfast, who remarked that they sounded 'rather dull'. I fear she may have been referring to my delivery rather than the historical events themselves. Most vexing.",

            "A veritable cavalcade of human endeavour and folly. One can scarcely decide which is more abundant in our species' history - ingenuity or utter incompetence. Both seem to feature prominently.",

            "History, as they say, is just one damned thing after another. Today appears to have been particularly well-supplied with damned things."
        ]

        return f"@here {events_text}{random.choice(closing_remarks)}"
