import logging
import time
import google.generativeai as genai
from google.generativeai.types import GenerateContentResponse

from PySubtitle.Helpers import FormatMessages
from PySubtitle.SubtitleError import NoTranslationError, TranslationAbortedError, TranslationError, TranslationFailedError, TranslationImpossibleError
from PySubtitle.Translation import Translation
from PySubtitle.TranslationClient import TranslationClient
from PySubtitle.TranslationParser import TranslationParser
from PySubtitle.TranslationPrompt import TranslationPrompt

class GeminiClient(TranslationClient):
    """
    Handles communication with Google Gemini to request translations
    """
    def __init__(self, settings : dict):
        super().__init__(settings)

        genai.configure(api_key=self.api_key)
        
        logging.info(f"Translating with Gemini {self.model or 'default'} model")

        self.gemini_model = genai.GenerativeModel(self.model)
        self.safety_settings = {
            "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
            "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
            "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
            "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",            
        }

    @property
    def api_key(self):
        return self.settings.get('api_key')
    
    @property
    def model(self):
        return self.settings.get('model')
    
    @property
    def rate_limit(self):
        return self.settings.get('rate_limit')
    
    def _request_translation(self, prompt : TranslationPrompt, temperature : float = None) -> Translation:
        """
        Request a translation based on the provided prompt
        """
        logging.debug(f"Messages:\n{FormatMessages(prompt.messages)}")

        temperature = temperature or self.temperature
        content = self._send_messages(prompt.messages, temperature)

        return Translation(content)
    
    def _abort(self):
        # TODO cancel any ongoing requests
        return super()._abort()

    def GetParser(self):
        return TranslationParser(self.settings)
    
    def _send_messages(self, messages : list, temperature):
        """
        Make a request to the Gemini API to provide a translation
        """
        content = {}

        prompt = self._build_prompt(messages)

        for retry in range(self.max_retries):
            if self.aborted:
                raise TranslationAbortedError()

            try:
                config = genai.GenerationConfig(candidate_count=1, temperature=temperature)
                response : GenerateContentResponse = self.gemini_model.generate_content(prompt, 
                                                                                        generation_config=config, 
                                                                                        safety_settings=self.safety_settings)

                if self.aborted:
                    raise TranslationAbortedError()
                
                if response.prompt_feedback.block_reason:
                    raise TranslationFailedError(f"Request was blocked by Gemini: {str(response.prompt_feedback.block_reason)}", response.prompt_feedback)

                if not response.candidates:
                    raise TranslationFailedError("No candidates returned in the response", response)

                # Try to find a validate candidate
                candidates = [candidate for candidate in response.candidates if candidate.finish_reason == "STOP"] or response.candidates

                candidate = candidates[0]
                content['token_count'] = candidate.token_count

                finish_reason = candidate.finish_reason
                if finish_reason == "STOP":
                    content['finish_reason'] = "complete"
                elif finish_reason == "MAX_TOKENS":
                    content['finish_reason'] = "length"
                    raise TranslationFailedError("Gemini response exceeded token limit", candidate)
                elif finish_reason == "SAFETY":
                    content['finish_reason'] = "blocked"
                    raise TranslationFailedError("Gemini response was blocked for safety reasons", candidate.safety_ratings)
                elif finish_reason == "RECITATION":
                    content['finish_reason'] = "recitation"
                    raise TranslationFailedError("Gemini response was blocked for recitation", candidate)
                elif finish_reason == "FINISH_REASON_UNSPECIFIED":
                    content['finish_reason'] = "unspecified"
                    raise TranslationError("Gemini response was incomplete", candidate)
                else:
                    # Probably a failure
                    content['finish_reason'] = finish_reason

                response_text = "\n".join(part.text for part in candidate.content.parts)

                if not response_text:
                    raise NoTranslationError("Gemini response is empty", response)

                content['text'] = response_text

                return content

            except (TranslationAbortedError, TranslationFailedError, TranslationImpossibleError):
                raise

            except Exception as e:
                logging.warning(f"Gemini request failure {str(e)}, trying to reconnect...")
                sleep_time = self.backoff_time * 2.0**retry
                logging.warning(f"OpenAI error {str(e)}, retrying in {sleep_time}...")
                time.sleep(sleep_time)
                
                self.gemini_model = genai.GenerativeModel(self.model)

        raise TranslationImpossibleError(f"Unexpected error communicating with Gemini", content, error=e)

    def _build_prompt(self, messages : list):
        """ Build a prompt from the messages """
        # Gemini doesn't support system messages natively, so prepare the script for a completion request
        return "\n\n".join([ f"#{m.get('role')} ###\n{m.get('content')}" for m in messages ])
