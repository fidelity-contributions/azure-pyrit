# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import pathlib

from pyrit.common.path import DATASETS_PATH
from pyrit.models import SeedPrompt
from pyrit.prompt_converter.fuzzer_converter.fuzzer_converter_base import (
    FuzzerConverter,
)
from pyrit.prompt_target import PromptChatTarget


class FuzzerSimilarConverter(FuzzerConverter):
    """
    Generates versions of a prompt with similar sentences.
    """

    def __init__(self, *, converter_target: PromptChatTarget, prompt_template: SeedPrompt = None):
        prompt_template = (
            prompt_template
            if prompt_template
            else SeedPrompt.from_yaml_file(
                pathlib.Path(DATASETS_PATH) / "prompt_converters" / "fuzzer_converters" / "similar_converter.yaml"
            )
        )
        super().__init__(converter_target=converter_target, prompt_template=prompt_template)
