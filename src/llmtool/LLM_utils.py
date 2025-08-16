# Imports
from openai import *
from pathlib import Path
from typing import Tuple
import google.generativeai as genai
from zhipuai import ZhipuAI
import anthropic
import signal
import sys
import tiktoken
import time
import os
import concurrent.futures
from functools import partial
import threading

import json
 # FIXME: an issue when installing botocore and boto3. I comment this function temporarily.
#from botocore.config import Config
#from botocore.exceptions import BotoCoreError, ClientError
# import boto3
from ui.logger import Logger


class LLM:
    """
    An online inference model using different LLMs:
    - Gemini
    - OpenAI: GPT-3.5, GPT-4, o3-mini
    - DeepSeek: V3, R1 (uses OpenAI-compatible API)
    - Claude: 3.5 and 3.7 (via API key or AWS Bedrock)
    - GLM: Zhipu AI models
    """

    def __init__(
        self,
        online_model_name: str,
        logger: Logger,
        temperature: float = 0.0,
        system_role: str = "You are an experienced programmer and good at understanding programs written in mainstream programming languages.",
        max_output_length: int = 4096,
    ) -> None:
        self.online_model_name = online_model_name
        self.encoding = tiktoken.encoding_for_model(
            "gpt-3.5-turbo-0125"
        )  # We only use gpt-3.5 to measure token cost
        self.temperature = temperature
        self.systemRole = system_role
        self.logger = logger
        self.max_output_length = max_output_length
        return

    def infer(
        self, message: str, is_measure_cost: bool = False
    ) -> Tuple[str, int, int]:
        self.logger.print_log(self.online_model_name, "is running")
        output = ""
        if "gemini" in self.online_model_name:
            output = self.infer_with_gemini(message)
        elif "gpt" in self.online_model_name:
            output = self.infer_with_openai_model(message)
        elif "o3-mini" in self.online_model_name:
            output = self.infer_with_o3_mini_model(message)
        elif "claude" in self.online_model_name:
            output = self.infer_with_claude_key(message)
            # output = self.infer_with_claude_aws_bedrock(message)
        elif "deepseek" in self.online_model_name:
            output = self.infer_with_deepseek_model(message)
        elif "glm" in self.online_model_name:
            output = self.infer_with_glm_model(message)
        else:
            raise ValueError("Unsupported model name")

        input_token_cost = (
            0
            if not is_measure_cost
            else len(self.encoding.encode(self.systemRole))
            + len(self.encoding.encode(message))
        )
        output_token_cost = (
            0 if not is_measure_cost else len(self.encoding.encode(output))
        )
        return output, input_token_cost, output_token_cost

    def run_with_timeout(self, func, timeout):
        """Run a function with timeout that works in multiple threads"""
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(func)
            try:
                return future.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                ("Operation timed out")
                return ""
            except Exception as e:
                self.logger.print_log(f"Operation failed: {e}")
                return ""

    def infer_with_gemini(self, message: str) -> str:
        """Infer using the Gemini model from Google Generative AI"""
        gemini_model = genai.GenerativeModel("gemini-pro")

        def call_api():
            message_with_role = self.systemRole + "\n" + message
            safety_settings = [
                {
                    "category": "HARM_CATEGORY_DANGEROUS",
                    "threshold": "BLOCK_NONE",
                },
                # ...existing safety settings...
            ]
            response = gemini_model.generate_content(
                message_with_role,
                safety_settings=safety_settings,
                generation_config=genai.types.GenerationConfig(
                    temperature=self.temperature
                ),
            )
            return response.text

        tryCnt = 0
        while tryCnt < 5:
            tryCnt += 1
            try:
                output = self.run_with_timeout(call_api, timeout=50)
                if output:
                    self.logger.print_log("Inference succeeded...")
                    return output
            except Exception as e:
                self.logger.print_log(f"API error: {e}")
            time.sleep(2)

        return ""

    def infer_with_openai_model(self, message):
        """Infer using the OpenAI model"""
        api_key = os.environ.get("OPENAI_API_KEY").split(":")[0]
        model_input = [
            {"role": "system", "content": self.systemRole},
            {"role": "user", "content": message},
        ]

        def call_api():
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=self.online_model_name,
                messages=model_input,
                temperature=self.temperature,
            )
            return response.choices[0].message.content

        tryCnt = 0
        while tryCnt < 5:
            tryCnt += 1
            try:
                output = self.run_with_timeout(call_api, timeout=100)
                if output:
                    return output
            except Exception as e:
                self.logger.print_log(f"API error: {e}")
            time.sleep(2)

        return ""

    def infer_with_o3_mini_model(self, message):
        """Infer using the o3-mini model"""
        api_key = os.environ.get("OPENAI_API_KEY").split(":")[0]
        model_input = [
            {"role": "system", "content": self.systemRole},
            {"role": "user", "content": message},
        ]

        def call_api():
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=self.online_model_name, messages=model_input
            )
            return response.choices[0].message.content

        tryCnt = 0
        while tryCnt < 5:
            tryCnt += 1
            try:
                output = self.run_with_timeout(call_api, timeout=100)
                if output:
                    return output
            except Exception as e:
                self.logger.print_log(f"API error: {e}")
            time.sleep(2)

        return ""

    def infer_with_deepseek_model(self, message):
        """
        Infer using the DeepSeek model (V3, R1, etc.)
        DeepSeek uses OpenAI-compatible API format
        """
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            self.logger.print_log("DeepSeek API key not found in environment variables")
            return ""
            
        model_input = [
            {
                "role": "system",
                "content": self.systemRole,
            },
            {"role": "user", "content": message},
        ]

        def call_api():
            client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1")
            response = client.chat.completions.create(
                model=self.online_model_name,
                messages=model_input,
                temperature=self.temperature,
            )
            return response.choices[0].message.content

        tryCnt = 0
        while tryCnt < 5:
            tryCnt += 1
            try:
                output = self.run_with_timeout(call_api, timeout=300)
                if output:
                    return output
            except Exception as e:
                self.logger.print_log(f"DeepSeek API error: {e}")
            time.sleep(2)

        return ""

    def infer_with_claude_key(self, message):
        """
        Infer using the Claude model with API key
        """
        api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLAUDE_API_KEY")
        if not api_key:
            self.logger.print_log("Claude API key not found in environment variables")
            return ""
            
        model_input = [
            {"role": "user", "content": f"{self.systemRole}\n\n{message}"}
        ]

        def call_api():
            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model=self.online_model_name,
                max_tokens=4096,
                temperature=self.temperature,
                messages=model_input
            )
            return response.content[0].text

        tryCnt = 0
        while tryCnt < 5:
            tryCnt += 1
            try:
                output = self.run_with_timeout(call_api, timeout=300)
                if output:
                    return output
            except Exception as e:
                self.logger.print_log(f"Claude API error: {e}")
            time.sleep(2)

        return ""

    def infer_with_claude_aws_bedrock(self, message):
        """Infer using the Claude model via AWS Bedrock"""
        # FIXME: an issue when installing boto3. I comment this function temporarily.
        raise NotImplementedError("AWS Bedrock is not supported")
    
        timeout = 500
        model_input = [
            {
                "role": "assistant",
                "content": self.systemRole,
            },
            {"role": "user", "content": message},
        ]

        if "3.5" in self.online_model_name:
            model_id = "anthropic.claude-3-5-sonnet-20241022-v2:0"
            body = json.dumps(
                {
                    "messages": model_input,
                    "max_tokens": self.max_output_length,
                    "anthropic_version": "bedrock-2023-05-31",
                    "temperature": self.temperature,
                    "top_k": 50,
                }
            )
        if "3.7" in self.online_model_name:
            model_id = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
            body = json.dumps(
                {
                    "messages": model_input,
                    "max_tokens": self.max_output_length,
                    "thinking": {
                        "type": "enabled",
                        "budget_tokens": 2048,
                    },
                    "anthropic_version": "bedrock-2023-05-31",
                }
            )

        def call_api():
            client = boto3.client(
                "bedrock-runtime",
                region_name="us-west-2",
                config=Config(read_timeout=timeout),
            )
            response = (
                client.invoke_model(
                    modelId=model_id, contentType="application/json", body=body
                )["body"]
                .read()
                .decode("utf-8")
            )

            response = json.loads(response)

            if "3.5" in self.online_model_name:
                result = response["content"][0]["text"]
            if "3.7" in self.online_model_name:
                result = response["content"][1]["text"]
            return result

        tryCnt = 0
        while tryCnt < 5:
            tryCnt += 1
            try:
                output = self.run_with_timeout(call_api, timeout=timeout)
                if output:
                    return output
            except concurrent.futures.TimeoutError:
                self.logger.print_log(
                    f"Timeout occurred, increasing timeout for next attempt"
                )
                timeout = min(timeout * 1.5, 900)
            except Exception as e:
                self.logger.print_log(f"API error: {str(e)}")
            time.sleep(2)

        return ""

    def infer_with_glm_model(self, message):
        """Infer using the GLM model"""
        api_key = os.environ.get("GLM_API_KEY")
        model_input = [
            {"role": "system", "content": self.systemRole},
            {"role": "user", "content": message},
        ]

        def call_api():
            client = ZhipuAI(api_key=api_key)
            response = client.chat.completions.create(
                model=self.online_model_name,
                messages=model_input,
                temperature=self.temperature,
            )
            return response.choices[0].message.content

        tryCnt = 0
        while tryCnt < 5:
            tryCnt += 1
            try:
                output = self.run_with_timeout(call_api, timeout=100)
                if output:
                    # print("Raw response from GLM model: ", output)
                    return output
            except Exception as e:
                self.logger.print_log(f"API error: {e}")
            time.sleep(2)

        return ""
