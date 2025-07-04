# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import logging
import pathlib
import uuid
from textwrap import dedent
from typing import Optional

from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from pyrit.common.path import DATASETS_PATH
from pyrit.models import (
    PromptDataType,
    PromptRequestPiece,
    PromptRequestResponse,
    SeedPrompt,
)
from pyrit.prompt_converter import ConverterResult, PromptConverter
from pyrit.prompt_target import PromptChatTarget

logger = logging.getLogger(__name__)


class TranslationConverter(PromptConverter):
    """
    Translates prompts into different languages using an LLM.
    """

    def __init__(
        self,
        *,
        converter_target: PromptChatTarget,
        language: str,
        prompt_template: Optional[SeedPrompt] = None,
        max_retries: int = 3,
        max_wait_time_in_seconds: int = 60,
    ):
        """
        Initializes the converter with the target chat support, language, and optional prompt template.

        Args:
            converter_target (PromptChatTarget): The target chat support for the conversion which will translate.
            language (str): The language for the conversion. E.g. Spanish, French, leetspeak, etc.
            prompt_template (SeedPrompt, Optional): The prompt template for the conversion.
            max_retries (int): Maximum number of retries for the conversion.
            max_wait_time_in_seconds (int): Maximum wait time in seconds between retries.

        Raises:
            ValueError: If the language is not provided.
        """
        self.converter_target = converter_target

        # Retry strategy for the conversion
        self._max_retries = max_retries
        self._max_wait_time_in_seconds = max_wait_time_in_seconds

        # set to default strategy if not provided
        prompt_template = (
            prompt_template
            if prompt_template
            else SeedPrompt.from_yaml_file(
                pathlib.Path(DATASETS_PATH) / "prompt_converters" / "translation_converter.yaml"
            )
        )

        if not language:
            raise ValueError("Language must be provided for translation conversion")

        self.language = language.lower()

        self.system_prompt = prompt_template.render_template_value(languages=language)

    async def convert_async(self, *, prompt: str, input_type: PromptDataType = "text") -> ConverterResult:
        """
        Converts the given prompt by translating it using the converter target.

        Args:
            prompt (str): The prompt to be converted.

        Returns:
            ConverterResult: The result containing the generated version of the prompt.

        Raises:
            ValueError: If the input type is not supported.
        """

        conversation_id = str(uuid.uuid4())

        self.converter_target.set_system_prompt(system_prompt=self.system_prompt, conversation_id=conversation_id)

        if not self.input_supported(input_type):
            raise ValueError("Input type not supported")

        formatted_prompt = dedent(
            f"Translate the following to {self.language} between the begin and end tags:"
            "=== begin ===\n"
            f"{prompt}\n"
            "=== end ===\n"
        )

        logger.debug(f"Formatted Prompt: {formatted_prompt}")

        request = PromptRequestResponse(
            [
                PromptRequestPiece(
                    role="user",
                    original_value=prompt,
                    converted_value=formatted_prompt,
                    conversation_id=conversation_id,
                    sequence=1,
                    prompt_target_identifier=self.converter_target.get_identifier(),
                    original_value_data_type=input_type,
                    converted_value_data_type=input_type,
                    converter_identifiers=[self.get_identifier()],
                )
            ]
        )

        translation = await self._send_translation_prompt_async(request)
        return ConverterResult(output_text=translation, output_type="text")

    async def _send_translation_prompt_async(self, request) -> str:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential(multiplier=1, min=1, max=self._max_wait_time_in_seconds),
            retry=retry_if_exception_type(Exception),  # covers all exceptions
        ):
            with attempt:
                logger.debug(f"Attempt {attempt.retry_state.attempt_number} for translation")
                response = await self.converter_target.send_prompt_async(prompt_request=request)
                response_msg = response.get_value()
                return response_msg.strip()

        # when we exhaust all retries without success, raise an exception
        raise Exception(f"Failed to translate after {self._max_retries} attempts")

    def input_supported(self, input_type: PromptDataType) -> bool:
        return input_type == "text"

    def output_supported(self, output_type: PromptDataType) -> bool:
        return output_type == "text"
