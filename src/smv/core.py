import os
import re
import argparse
import xml.etree.ElementTree as ET
import time

# Assuming smv is in PYTHONPATH or running from src/
from smv import config
from smv.analyzers.image_analyzer import ImageAnalyzer
from smv.analyzers.text_analyzer import TextAnalyzer
from smv.utils import command_utils, file_utils, llm_utils


class SmartMover:
    """
    Manages the AI-driven file sorting process using an LLM to analyze
    a file and suggest organization actions. It leverages various utility
    modules for specialized tasks like file analysis, command execution, and LLM interaction.
    """

    def __init__(self, file_path_to_sort):
        self.file_path = os.path.abspath(file_path_to_sort)
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"File not found: {self.file_path}")
        if not os.path.isfile(self.file_path):
            raise ValueError(f"Path is not a file: {self.file_path}")

        self.llm_helper = llm_utils.LLMHelper(
            api_key=config.OPENAI_API_KEY,
            base_url=config.OPENAI_API_BASE_URL,
            model_name=config.MODEL_NAME,
            max_retries=config.MAX_LLM_RETRIES_ON_PARSE_ERROR,
        )
        self.file_summary = "Not yet summarized."
        self.home_dir = os.path.expanduser("~")
        self.trash_dir = os.path.join(self.home_dir, ".Trash")
        self.step3_suggestion_data = {}

        self.custom_instruction_prompt_addition = ""
        if config.CUSTOM_AI_INSTRUCTIONS and config.CUSTOM_AI_INSTRUCTIONS.strip():
            self.custom_instruction_prompt_addition = (
                f"\n\nIMPORTANT GENERAL GUIDELINES TO CONSIDER:\n"
                f"{config.CUSTOM_AI_INSTRUCTIONS.strip()}\n"
                f"---"
            )
        self.pypdf_installed, self.pillow_installed, self.pdf2image_installed = (
            config.check_dependencies()
        )

    def _call_llm_and_parse_xml_with_retry(
        self,
        original_messages,
        expected_root_tag,
        max_tokens_for_call,
        step_name="Unknown Step",
    ):
        """
        Calls LLM and parses XML, with retries on parsing failure.
        Uses LLMHelper for parsing and its own retry prompt logic.
        """
        for attempt in range(config.MAX_LLM_RETRIES_ON_PARSE_ERROR + 1):
            current_messages = list(original_messages)
            if attempt > 0:
                print(
                    f"Retrying LLM call for {step_name} (Attempt {attempt + 1}/{config.MAX_LLM_RETRIES_ON_PARSE_ERROR + 1}) due to previous parsing error."
                )
                retry_instruction = (
                    f" IMPORTANT: Your previous XML response had parsing errors. "
                    f"Please ensure your XML output is perfectly formed, complete, and adheres strictly to the requested schema, including the root tag <{expected_root_tag}>. "
                    f"Pay close attention to closing all tags and avoiding invalid characters or structures."
                )
                if current_messages and current_messages[0]["role"] == "system":
                    current_messages[0]["content"] += retry_instruction
                else:
                    current_messages.insert(
                        0,
                        {
                            "role": "system",
                            "content": f"You are an AI assistant.{retry_instruction}",
                        },
                    )

            response_str = self.llm_helper.call_llm(
                current_messages,
                temperature=config.LLM_TEMPERATURE,
                max_tokens=max_tokens_for_call,
            )
            print(response_str)
            if response_str is None:
                if attempt < config.MAX_LLM_RETRIES_ON_PARSE_ERROR:
                    continue
                else:
                    print(f"LLM call failed after all retries for {step_name}.")
                    return None

            # Use LLMHelper's parsing method
            parsed_xml = self.llm_helper.parse_xml_string(
                response_str, expected_root_tag
            )
            if parsed_xml is not None:
                return parsed_xml

            print(f"XML parsing failed for {step_name} on attempt {attempt + 1}.")
        print(f"Failed to parse XML for {step_name} after all retries.")
        return None

    def step1_initial_decision(self):
        print("\n--- Step 1: Initial Action Decision ---")
        file_age_desc = file_utils.get_file_age_description(self.file_path)
        _, ext = os.path.splitext(self.file_path)
        ext = ext.lower()

        archive_extracted_info = ""
        extracted_folder_path = file_utils.check_if_archive_extracted(
            self.file_path, config.ARCHIVE_EXTENSIONS
        )
        if extracted_folder_path:
            archive_extracted_info = (
                f"\nNote: This archive '{os.path.basename(self.file_path)}' appears to have already been extracted "
                f"into a folder named '{os.path.basename(extracted_folder_path)}' in the same directory, "
                f"and the extracted folder is newer or the same age. This makes the original archive a strong candidate for Trash."
            )

        deletable_type_consideration = ""
        if ext in config.DELETABLE_CANDIDATE_EXTENSIONS:
            deletable_type_consideration = (
                f"\nNote: This file type ({ext}) is often temporary or an installer. Its age ({file_age_desc}) "
                f"is a strong factor for considering 'move_to_trash' if it's in a temporary location like 'Downloads' and not brand new."
            )

        user_prompt_content = f"""
{self.custom_instruction_prompt_addition}
File path: '{self.file_path}' (Age: {file_age_desc})
{archive_extracted_info}
{deletable_type_consideration}

Considering the file's name, its current location (especially if it's in a temporary folder like 'Downloads'), its age, whether it's an already extracted archive or a potentially deletable type, and any general guidelines, what is your initial assessment?
- If the file is in a common temporary location (like 'Downloads') and isn't extremely recent (e.g., not 'modified just now' or 'modified today'), it should likely be moved ('move_to_folder' or 'move_to_trash'), even if it appears important. 'stay' is less appropriate.
- If you cannot tell if the file is important or not, consider 'more_info' to gather more context.

**Reasoning Guidance:** Explain your thought process thoroughly in 3 sentences. Why did you choose this action over others? What specific file characteristics (name, type, age, location) or contextual clues (like being an extracted archive or an old installer in Downloads) led to this decision?
- Options: 'move_to_trash', 'move_to_folder', 'stay', 'more_info'.

Provide a confidence score (0.0-1.0).
Output XML, ensuring a single root tag `<assessment>`:
<assessment>
    <reasoning>Detailed reasoning for the chosen action, explaining the factors considered and why this action is most appropriate.</reasoning>
    <action>move_to_trash|move_to_folder|stay|more_info</action>
    <confidence>0.X</confidence>
</assessment>
        """
        messages = [
            {
                "role": "system",
                "content": "You are a file organization assistant. Provide an initial assessment with detailed reasoning.",
            },
            {"role": "user", "content": user_prompt_content.strip()},
        ]

        parsed_xml = self._call_llm_and_parse_xml_with_retry(
            messages,
            "assessment",
            max_tokens_for_call=config.MAX_TOKENS_STEP1,
            step_name="Step 1",
        )

        if parsed_xml is not None:
            action = parsed_xml.findtext("action")
            confidence = float(parsed_xml.findtext("confidence", "0.0"))
            reasoning = parsed_xml.findtext("reasoning", "No reasoning provided.")
            if action:
                self.llm_helper.update_context(
                    f"Step 1: Initial assessment for '{os.path.basename(self.file_path)}' (Age: {file_age_desc}) is '{action}' with confidence {confidence:.2f}. Reason: {reasoning}"
                )
                return {
                    "action": action,
                    "confidence": confidence,
                    "reasoning": reasoning,
                }

        self.llm_helper.update_context(
            f"Step 1: Failed to get a clear initial assessment for '{os.path.basename(self.file_path)}' (Age: {file_age_desc})."
        )
        return None

    def step2_summarize_file(self):
        print("\n--- Step 2: File Summarization ---")
        file_content_for_llm_parts = []
        text_for_llm_prompt = ""
        _, ext = os.path.splitext(self.file_path)
        ext = ext.lower()
        meaningful_text_extracted = False
        image_data_prepared = False
        file_age_desc = file_utils.get_file_age_description(self.file_path)

        file_type_guess = TextAnalyzer.get_file_type_description(self.file_path)
        text_for_llm_prompt += (
            f"Initial file type guess: {file_type_guess}. File age: {file_age_desc}.\n"
        )

        if config.ALLOW_LLM_FILE_PROCESSING:
            try:
                file_size_bytes = os.path.getsize(self.file_path)
                process_content = True

                if ext == ".pdf":
                    if file_size_bytes > (
                        config.MAX_FILE_SIZE_FOR_FULL_PROCESSING_MB * 1024 * 1024
                    ):
                        print(
                            f"PDF size {file_size_bytes / (1024 * 1024):.2f}MB is large, but attempting text extraction (up to {config.MAX_EXTRACTED_TEXT_SIZE_KB}KB)."
                        )
                    if self.pypdf_installed:
                        success, pdf_text_content = TextAnalyzer.extract_from_pdf(
                            self.file_path, config.MAX_EXTRACTED_TEXT_SIZE_KB
                        )
                        if success:
                            if (
                                pdf_text_content
                                and len(pdf_text_content.strip())
                                >= config.MIN_MEANINGFUL_TEXT_LENGTH
                            ):
                                text_for_llm_prompt += f"Extracted text from PDF (up to {config.MAX_EXTRACTED_TEXT_SIZE_KB}KB):\n```\n{pdf_text_content.strip()}\n```\n"
                                meaningful_text_extracted = True
                            else:
                                text_for_llm_prompt += f"PDF text extraction using pypdf yielded no meaningful content (content: '{pdf_text_content[:100]}...'). "
                        else:
                            text_for_llm_prompt += f"Could not extract text from PDF using pypdf. Error: {pdf_text_content}. "
                    else:
                        text_for_llm_prompt += (
                            "pypdf not installed, PDF text extraction skipped. "
                        )

                elif TextAnalyzer.is_text_file(self.file_path):
                    if file_size_bytes > (
                        config.MAX_FILE_SIZE_FOR_FULL_PROCESSING_MB * 1024 * 1024
                    ):
                        text_for_llm_prompt += (
                            "Text file is too large for full content processing. "
                        )
                        process_content = False
                    if process_content:
                        success, text_content = TextAnalyzer.extract_from_text_file(
                            self.file_path, config.MAX_EXTRACTED_TEXT_SIZE_KB
                        )
                        if success:
                            if (
                                text_content
                                and len(text_content.strip())
                                >= config.MIN_MEANINGFUL_TEXT_LENGTH
                            ):
                                text_for_llm_prompt += f"Full text content (up to {config.MAX_EXTRACTED_TEXT_SIZE_KB}KB):\n```\n{text_content.strip()}\n```\n"
                                meaningful_text_extracted = True
                            else:
                                text_for_llm_prompt += (
                                    "Text file content too short to be meaningful. "
                                )
                        else:
                            text_for_llm_prompt += f"Could not read text file content. Error: {text_content}. "

                elif ImageAnalyzer.is_image_file(self.file_path):
                    if file_size_bytes > (
                        config.MAX_FILE_SIZE_FOR_FULL_PROCESSING_MB * 1024 * 1024
                    ):
                        text_for_llm_prompt += (
                            "Image file is too large for full processing. "
                        )
                        process_content = False
                else:
                    if ext not in config.ARCHIVE_EXTENSIONS and ext not in [
                        ".pkg",
                        ".dmg",
                        ".exe",
                    ]:
                        if file_size_bytes > (
                            config.MAX_FILE_SIZE_FOR_FULL_PROCESSING_MB * 1024 * 1024
                        ):
                            text_for_llm_prompt += (
                                "File is too large for full content processing. "
                            )
                        else:
                            text_for_llm_prompt += (
                                "File type not suitable for direct text extraction. "
                            )

                if (
                    process_content
                    and config.ALLOW_LLM_IMAGE_PROCESSING
                    and self.pillow_installed
                ):
                    base64_image_str = None
                    image_source_description = ""
                    if (
                        ext == ".pdf"
                        and not meaningful_text_extracted
                        and self.pdf2image_installed
                    ):
                        base64_image_str = ImageAnalyzer.pdf_to_image(
                            self.file_path,
                            config.MAX_IMAGE_RESOLUTION_FOR_LLM,
                            config.IMAGE_QUALITY_FOR_LLM,
                            page=1,
                        )
                        if base64_image_str:
                            image_source_description = (
                                "First page of PDF processed as image. "
                            )
                    elif ImageAnalyzer.is_image_file(self.file_path):
                        base64_image_str = ImageAnalyzer.process_image(
                            self.file_path,
                            config.MAX_IMAGE_RESOLUTION_FOR_LLM,
                            config.IMAGE_QUALITY_FOR_LLM,
                        )
                        if base64_image_str:
                            image_source_description = (
                                "Image file content being processed. "
                            )

                    if base64_image_str:
                        text_for_llm_prompt += image_source_description
                        file_content_for_llm_parts.append(
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image_str}"
                                },
                            }
                        )
                        image_data_prepared = True
                        print("Image data prepared for LLM.")
                    elif image_source_description:
                        text_for_llm_prompt += "Could not obtain image data for processing after attempting. "

                if (
                    not meaningful_text_extracted
                    and not image_data_prepared
                    and process_content
                ):
                    if not text_for_llm_prompt.strip().endswith(". "):
                        text_for_llm_prompt += ". "
                    text_for_llm_prompt += "No detailed content (text or image) was successfully prepared. Summary will rely on filename, type, and age. "
            except Exception as e:
                text_for_llm_prompt += f"Error accessing file for processing: {e}. "
        else:
            text_for_llm_prompt += "Full file content processing is disabled. "

        final_text_prompt_for_llm = f"""
        File name: '{os.path.basename(self.file_path)}'; File path: '{self.file_path}'
        Context:
        {text_for_llm_prompt.strip()}

        **Summarization Instructions:**
        Based on all the information  above, provide a detailed summary of the file's **overall nature** and **content**.
        The goal is a detailed informative summary with some key details quoted, like title, heading, author... Output in one paragraph. 
        """.strip()

        final_content_for_api = [{"type": "text", "text": final_text_prompt_for_llm}]
        if image_data_prepared:
            final_content_for_api.extend(file_content_for_llm_parts)

        messages = [
            {
                "role": "system",
                "content": "You are a file analysis assistant. Summarize the file's nature and significance based ONLY on provided content.",
            },
            {
                "role": "user",
                "content": final_content_for_api
                if image_data_prepared
                else final_text_prompt_for_llm,
            },
        ]

        summary = self.llm_helper.call_llm(
            messages, temperature=config.LLM_TEMPERATURE, max_tokens=200
        )
        self.file_summary = (
            summary
            if summary
            else f"Summary not generated. {file_type_guess} (Age: {file_age_desc})"
        )
        self.llm_helper.update_context(f"File summary: {self.file_summary}")
        return self.file_summary

    def _rank_filenames_by_keywords(self, filenames, keywords_str):
        if not keywords_str or not filenames:
            return filenames
        keywords = [kw.lower().strip() for kw in keywords_str.split(",") if kw.strip()]
        if not keywords:
            return filenames
        scored_filenames = []
        for fn_info in filenames:
            fn_str = fn_info if isinstance(fn_info, str) else fn_info.get("name", "")
            if not fn_str or fn_str in config.FILES_TO_IGNORE_IN_LS:
                continue
            score = sum(1 for kw in keywords if kw in fn_str.lower())
            scored_filenames.append(
                {"name": fn_str, "score": score, "original_info": fn_info}
            )
        scored_filenames.sort(key=lambda x: (-x["score"], x["name"]))
        return [item["name"] for item in scored_filenames]

    def _filter_keywords(self, keywords_str, extensions_to_filter):
        if not keywords_str:
            return ""
        keywords = [kw.strip() for kw in keywords_str.split(",") if kw.strip()]
        return ", ".join(
            [
                kw
                for kw in keywords
                if not (
                    kw.lower().lstrip(".") in extensions_to_filter
                    or kw.lower() in extensions_to_filter
                )
            ]
        )

    def step3_get_candidates_and_keywords(self):
        print("\n--- Step 3: Candidate Folder and Keyword Generation ---")
        file_age_desc = file_utils.get_file_age_description(self.file_path)
        success, home_contents_stdout, _ = command_utils.run_shell_command(
            ["ls", "-pA1", self.home_dir]
        )
        top_level_folders = []
        if success and home_contents_stdout:
            top_level_folders = [
                os.path.join(self.home_dir, i.strip().rstrip("/"))
                for i in home_contents_stdout.splitlines()
                if i.endswith("/")
                and i.strip() not in ["./", "../"]
                and not (config.IGNORE_HIDDEN_FOLDERS and i.startswith("."))
            ]
        common_dirs = [
            "Documents",
            "Downloads",
            "Pictures",
            "Movies",
            "Desktop",
            "Music",
            "Videos",
            "Development",
            "Projects",
            "Work",
            "Applications",
        ]
        for d in common_dirs:
            fp = os.path.join(self.home_dir, d)
            if (
                os.path.isdir(fp)
                and fp not in top_level_folders
                and not (config.IGNORE_HIDDEN_FOLDERS and d.startswith("."))
            ):
                top_level_folders.append(fp)
        if os.path.isdir(self.trash_dir) and self.trash_dir not in top_level_folders:
            top_level_folders.append(self.trash_dir)
        top_level_folders_str = "\n".join(sorted(list(set(top_level_folders))))

        user_prompt_content = f"""
{self.custom_instruction_prompt_addition}
{self.llm_helper.current_context}

File to sort: '{os.path.basename(self.file_path)}' (Age: {file_age_desc})
Full path: '{self.file_path}'
File summary: '{self.file_summary}'

Available top-level user folders (and Trash) to consider for initiating search:
---
{top_level_folders_str[:2000]} 
---
Tasks:
1.  **Candidate Search Paths:** Suggest initial candidate top-level folders (comma-separated full paths from the list) to search within. If Trash seems appropriate, include '{config.TRASH_DESTINATION_IDENTIFIER}'.
2.  **Folder Keywords:** Generate relevant folder search keywords. Consider the file's nature. Include singular/plural forms. Do NOT use file extensions.
3.  **File Keywords:** Generate relevant file search keywords from summary/filename. Include singular/plural forms. Do NOT use file extensions.
4.  **Reasoning:** Provide detailed reasoning (multiple sentences) for your choices of search paths and keywords. Explain *why* these are good starting points.
5.  **Confidence Scores:** Provide confidence scores (0.0-1.0) for paths, folder keywords, and file keywords.

Output XML, ensuring a single root tag `<search_parameters>`:
<search_parameters>
    <reasoning>Detailed justification for suggested search paths and keywords, explaining the thought process.</reasoning>
    <candidate_search_paths confidence="0.X">/path/folder1,{config.TRASH_DESTINATION_IDENTIFIER}</candidate_search_paths>
    <folder_keywords confidence="0.Y">kw_folder1, kw_folder2</folder_keywords>
    <file_keywords confidence="0.Z">kw_fileA, kw_fileB</file_keywords>
</search_parameters>
        """
        messages = [
            {
                "role": "system",
                "content": "You are a file organization expert. Suggest search parameters with detailed reasoning. Do not use file extensions as keywords.",
            },
            {"role": "user", "content": user_prompt_content.strip()},
        ]
        parsed_xml = self._call_llm_and_parse_xml_with_retry(
            messages,
            "search_parameters",
            max_tokens_for_call=config.MAX_TOKENS_STEP3,
            step_name="Step 3",
        )

        if parsed_xml is not None:
            reasoning = parsed_xml.findtext("reasoning", "No reasoning provided.")
            self.llm_helper.update_context(f"Step 3 Reasoning: {reasoning}")
            paths_el, fk_el, filek_el = (
                parsed_xml.find("candidate_search_paths"),
                parsed_xml.find("folder_keywords"),
                parsed_xml.find("file_keywords"),
            )

            def get_text(el):
                return el.text if el is not None else None

            def get_conf(el):
                return float(el.get("confidence", "0.0")) if el is not None else 0.0

            final_fk = self._filter_keywords(
                get_text(fk_el), config.COMMON_FILE_EXTENSIONS_TO_FILTER
            )
            final_fk = ", ".join(
                kw
                for kw in final_fk.split(", ")
                if len(kw.strip()) >= config.MIN_KEYWORD_LENGTH and kw.strip()
            )
            final_filek = self._filter_keywords(
                get_text(filek_el), config.COMMON_FILE_EXTENSIONS_TO_FILTER
            )
            final_filek = ", ".join(
                kw
                for kw in final_filek.split(", ")
                if len(kw.strip()) >= config.MIN_KEYWORD_LENGTH and kw.strip()
            )

            self.step3_suggestion_data = {
                "folders_str": get_text(paths_el),
                "folders_confidence": get_conf(paths_el),
                "folder_keywords_str": final_fk,
                "folder_keywords_confidence": get_conf(fk_el),
                "file_keywords_str": final_filek,
                "file_keywords_confidence": get_conf(filek_el),
            }
            return self.step3_suggestion_data
        return None

    def step4_execute_search(
        self, search_paths, folder_keywords_str, file_keywords_str
    ):
        print(f"\n--- Step 4: Executing Search ---")
        results = {"folder_matches": set(), "file_matches": set()}
        actual_search_paths = [
            p
            for p in search_paths
            if p != config.TRASH_DESTINATION_IDENTIFIER and os.path.isdir(p)
        ]
        if not actual_search_paths:
            print("No valid filesystem search paths for Step 4.")
            return results
        print(
            f"Searching in: {actual_search_paths}; FolderKW: '{folder_keywords_str}'; FileKW: '{file_keywords_str}'"
        )

        if folder_keywords_str:
            opts = command_utils.build_keyword_options(folder_keywords_str)
            if opts:
                cmd = command_utils.build_find_command_parts(
                    actual_search_paths,
                    opts,
                    find_type="d",
                    excluded_patterns=config.EXCLUDED_DIRS_FIND_PATTERNS,
                )
                if cmd:
                    success, stdout, _ = command_utils.run_shell_command(cmd)
                    if success and stdout:
                        [
                            results["folder_matches"].add(os.path.normpath(l.strip()))
                            for l in stdout.splitlines()
                            if l.strip()
                        ]
        if file_keywords_str:
            opts = command_utils.build_keyword_options(file_keywords_str)
            if opts:
                cmd = command_utils.build_find_command_parts(
                    actual_search_paths,
                    opts,
                    find_type="f",
                    excluded_patterns=config.EXCLUDED_DIRS_FIND_PATTERNS,
                    print0=True,
                )
                if cmd:
                    success, stdout, _ = command_utils.run_shell_command(cmd)
                    if success and stdout:
                        [
                            results["file_matches"].add(
                                os.path.dirname(os.path.normpath(fp.strip()))
                            )
                            for fp in stdout.split("\0")
                            if fp.strip()
                        ]
        return results

    def _score_and_rank_found_paths(self, found_paths_dict):
        path_scores = {}
        for path_type, score_val in [("folder_matches", 2), ("file_matches", 1)]:
            for path in found_paths_dict.get(path_type, set()):
                path_scores.setdefault(path, {"score": 0, "match_types": set()})
                path_scores[path]["score"] += score_val
                path_scores[path]["match_types"].add(
                    "direct_folder"
                    if path_type == "folder_matches"
                    else "contains_file"
                )
        ranked = [{"path": p, **details} for p, details in path_scores.items()]
        ranked.sort(key=lambda x: x["score"], reverse=True)
        return [item["path"] for item in ranked]

    # Step 4.5 _step4_5_pre_filter_paths is removed. Truncation logic moved to sort_file.

    def step6_process_search_results(
        self, search_results_data, paths_were_truncated=False, user_hint_for_prompt=None
    ):
        print(f"\n--- Step 6: Processing Search Results ---")
        # search_results_data is now always a list of dicts
        if not search_results_data:
            if (
                config.TRASH_DESTINATION_IDENTIFIER in self.llm_helper.current_context
                or (
                    hasattr(self, "step3_suggestion_data")
                    and self.step3_suggestion_data
                    and config.TRASH_DESTINATION_IDENTIFIER
                    in self.step3_suggestion_data.get("folders_str", "")
                )
            ):
                print(
                    "No filesystem paths to process, but Trash was considered. Proposing Trash."
                )
                return [
                    {
                        "rank": 1,
                        "confidence": config.HIGH_CONFIDENCE,
                        "path": config.TRASH_DESTINATION_IDENTIFIER,
                        "type": "trash_bin",
                    }
                ]
            return None

        final_paths_for_llm_prompt = []
        for i, item in enumerate(
            search_results_data
        ):  # search_results_data is list of dicts
            desc = (
                config.TRASH_DESTINATION_IDENTIFIER
                if item["path"] == config.TRASH_DESTINATION_IDENTIFIER
                else item["path"]
            )
            if item.get("type") == "trash_bin":
                desc += " (User's Trash)"
            # Add confidence if available from pre-filtering (though pre-filter LLM is removed, source might still be useful)
            if (
                "source" in item and item["source"] != "heuristic_ranked_all"
            ):  # e.g. heuristic_truncate
                desc += f" (Source: {item['source']}, Heuristic Conf: {item.get('confidence', 0):.2f})"
            final_paths_for_llm_prompt.append(f"{i + 1}. {desc}")

        source_desc = (
            "Paths (truncated by heuristic ranking):"
            if paths_were_truncated
            else "Paths (heuristically ranked):"
        )
        paths_str = "\n".join(
            final_paths_for_llm_prompt[: config.MAX_PATHS_TO_STEP6_LLM]
        )
        hint_section = (
            f"\nUser's refinement hint: {user_hint_for_prompt}\n"
            if user_hint_for_prompt
            else ""
        )

        user_prompt_content = f"""
{self.custom_instruction_prompt_addition}
{self.llm_helper.current_context}
{hint_section}
File to sort: '{os.path.basename(self.file_path)}' (Summary: '{self.file_summary}')
{source_desc}
---
{paths_str}
---
Choose up to 3 best destinations from this list, ranked by preference. 
If '{config.TRASH_DESTINATION_IDENTIFIER}' (User's Trash) seems most appropriate, list it with type 'trash_bin'.

**Reasoning Guidance:** Explain your overall reasoning (multiple sentences) for the top choices. Why are these specific paths the best fit for the file, considering its summary, name, and the context provided about the paths?
Output XML, ensuring a single root tag `<target_destination>`:
<target_destination>
    <reasoning_overall>Detailed overall reasoning for the selection of top target destinations.</reasoning_overall>
    <folder rank="1" confidence="0.X" type="directory_or_trash_bin">/path/to/best or {config.TRASH_DESTINATION_IDENTIFIER}</folder>
    <folder rank="2" confidence="0.Y" type="directory">/path/to/second_best</folder> 
</target_destination> 
        """
        messages = [
            {
                "role": "system",
                "content": "You are a file organization expert. Choose best target destinations with detailed reasoning.",
            },
            {"role": "user", "content": user_prompt_content.strip()},
        ]
        parsed_xml = self._call_llm_and_parse_xml_with_retry(
            messages,
            "target_destination",
            max_tokens_for_call=config.MAX_TOKENS_STEP6,
            step_name="Step 6",
        )

        if parsed_xml is None:
            print("Step 6 LLM call failed.")
            return None
        suggestions = []
        reasoning = parsed_xml.findtext(
            "reasoning_overall", "No Step 6 reasoning provided."
        )
        self.llm_helper.update_context(f"Step 6 Reasoning: {reasoning}")
        for el in parsed_xml.findall("folder"):
            path_text, path_type = (
                (el.text.strip() if el.text else None),
                el.get("type", "directory"),
            )
            if path_text:
                path_text = re.sub(
                    r"^\d+\.\s*",
                    "",
                    re.sub(
                        r"\s*\(Source:.*?Conf:.*?\)$",
                        "",
                        path_text,
                        flags=re.IGNORECASE,
                    ),
                ).strip()  # Clean up potential prefixes/suffixes
                is_valid = (
                    (path_text == config.TRASH_DESTINATION_IDENTIFIER)
                    or (path_type != "trash_bin" and os.path.isdir(path_text))
                    or (
                        path_type == "trash_bin"
                        and path_text == config.TRASH_DESTINATION_IDENTIFIER
                    )
                )
                if is_valid:
                    suggestions.append(
                        {
                            "rank": int(el.get("rank", "99")),
                            "confidence": float(el.get("confidence", "0.0")),
                            "path": path_text,
                            "type": "trash_bin"
                            if path_text == config.TRASH_DESTINATION_IDENTIFIER
                            else path_type,
                        }
                    )
                elif path_text:
                    print(
                        f"Warning: LLM suggested invalid path '{path_text}' (type: {path_type}) in Step 6."
                    )
        if not suggestions and parsed_xml is not None:
            print("Step 6 LLM returned no valid folder suggestions.")
        return sorted(suggestions, key=lambda x: (x["rank"], -x["confidence"]))

    def step7_final_confirmation(self, target_suggestions, allow_hint_option=True):
        print("\n--- Step 7: Final Confirmation ---")
        if not target_suggestions:
            return {"action": "error", "reasoning": "No suggestions to Step 7."}
        plausible = sorted(
            [
                s
                for s in target_suggestions
                if s["confidence"] >= config.MEDIUM_CONFIDENCE
            ],
            key=lambda x: x["confidence"],
            reverse=True,
        )
        chosen_eval = None

        if len(plausible) > 1:
            msg = (
                f"\nAI identified multiple plausible targets for '{os.path.basename(self.file_path)}':\n"
                + "\n".join(
                    [
                        f"  {i + 1}. {config.TRASH_DESTINATION_IDENTIFIER if s['path'] == config.TRASH_DESTINATION_IDENTIFIER else s['path']} (Conf: {s['confidence']:.2f}, Type: {s.get('type', 'dir')})"
                        for i, s in enumerate(plausible)
                    ]
                )
                + "\nChoose by number, 'D' for AI top choice, "
                + ("'M' for hint, " if allow_hint_option else "")
                + "or 'R' to reject: "
            )
            print(msg.strip())
            while True:
                choice = input().strip().lower()
                if choice == "d":
                    chosen_eval = plausible[0]
                    print(f"User opted AI choice: {chosen_eval['path']}")
                    break
                elif choice == "r":
                    return {"action": "error", "reasoning": "User rejected all."}
                elif choice == "m" and allow_hint_option:
                    hint = input("Hint for AI: ").strip()
                    if hint:
                        return {"action": "user_provided_hint", "hint": hint}
                    else:
                        print("No hint given.")
                else:
                    try:
                        idx = int(choice) - 1
                        if 0 <= idx < len(plausible):
                            chosen_eval = plausible[idx]
                            print(f"User selected: {chosen_eval['path']}")
                            break
                        else:
                            print("Invalid number.")
                    except ValueError:
                        print("Invalid input.")
        elif len(plausible) == 1:
            chosen_eval = plausible[0]
            print(f"One plausible suggestion: {chosen_eval['path']}")
        else:
            return {
                "action": "error",
                "reasoning": "No suggestions met medium confidence.",
            }
        if chosen_eval is None:
            return {"action": "error", "reasoning": "Failed to select suggestion."}

        target_path, target_type = (
            chosen_eval["path"],
            chosen_eval.get("type", "directory"),
        )
        file_age_desc = file_utils.get_file_age_description(self.file_path)
        print(
            f"\nEvaluating chosen target: '{target_path}' (Type: {target_type}, Conf: {chosen_eval['confidence']:.2f})"
        )
        ls_out = f"Target is '{config.TRASH_DESTINATION_IDENTIFIER}'. Contents N/A."
        if target_path != config.TRASH_DESTINATION_IDENTIFIER:
            success, stdout, _ = command_utils.run_shell_command(
                ["ls", "-pA1", target_path]
            )
            if success and stdout:
                fns = [
                    f.rstrip("/")
                    for f in stdout.splitlines()
                    if f.strip()
                    and f not in ["./", "../"]
                    and f not in config.FILES_TO_IGNORE_IN_LS
                    and not (config.IGNORE_HIDDEN_FOLDERS and f.startswith("."))
                ]
                kw = (
                    self.step3_suggestion_data.get("file_keywords_str", "")
                    if hasattr(self, "step3_suggestion_data")
                    and self.step3_suggestion_data
                    else ""
                )
                ranked_fns = self._rank_filenames_by_keywords(fns, kw)
                rel_fns, other_fns = (
                    ranked_fns[: config.MAX_LS_OUTPUT_FILES_TO_SHOW_LLM],
                    [
                        f
                        for f in ranked_fns[config.MAX_LS_OUTPUT_FILES_TO_SHOW_LLM :]
                        if f not in ranked_fns[: config.MAX_LS_OUTPUT_FILES_TO_SHOW_LLM]
                    ][: config.MAX_LS_OUTPUT_OTHER_FILES],
                )
                parts = []
                if rel_fns:
                    parts.append(
                        f"Related (top {len(rel_fns)}):\n"
                        + "\n".join([f"  - {f}" for f in rel_fns])
                    )
                if other_fns:
                    parts.append(
                        f"Other (sample):\n"
                        + "\n".join([f"  - {f}" for f in other_fns])
                    )
                if len(fns) > len(rel_fns) + len(other_fns):
                    parts.append(
                        f"...and {len(fns) - (len(rel_fns) + len(other_fns))} more."
                    )
                ls_out = (
                    "\n".join(parts)
                    if parts
                    else "[Folder empty or only ignored items.]"
                )
            else:
                ls_out = "[Folder empty or inaccessible]"
            print(f"Contents of '{target_path}':\n{ls_out[:1000]}...")

        user_prompt_content = f"""
{self.custom_instruction_prompt_addition}
{self.llm_helper.current_context}
File to sort: '{os.path.basename(self.file_path)}' (Summary: '{self.file_summary}', Age: {file_age_desc})
Chosen target: '{target_path}' (Type: {target_type})
Target contents (if applicable):
---
{ls_out[:2000] if target_path != config.TRASH_DESTINATION_IDENTIFIER else "N/A - Target is Trash"}
---
The target destination ('{target_path}') has been selected. Your task is to finalize how the file should be placed here.

1.  **Action Confirmation:**
    * If the target is '{config.TRASH_DESTINATION_IDENTIFIER}', the core action is 'move_to_trash'. Renaming and subfolder creation are 'NA_for_Trash'.
    * If the target is a folder: Assume it's suitable unless its contents (previously listed) reveal a *new and critical conflict* (e.g., it's clearly a system-only folder). If such a conflict exists, the action is 'reject_folder'. Otherwise, proceed to determine subfolder/rename options and the corresponding move action.

2.  **For an Acceptable Folder Target – Refine Placement:**
    * **Subfolder Creation:** Suggest a new subfolder `Name` *only if truly essential* for organizing this specific file, or if there's strong evidence more related files will follow (e.g., 'Project_Invoices' for an invoice, 'Tax_2024' for a tax document). Otherwise, output 'No'. Be conservative with creating new folders for single files.
    * **File Renaming (Prioritize for good organization):**
        Current name: '{os.path.basename(self.file_path)}'.
        *Your primary goal here is to propose an improved, well-formatted, and descriptive new filename if the current one isn't optimal.**
        **Examine Existing Files & Match Pattern:** Look closely at the names of other files in the target folder. If a clear naming pattern or format is evident (e.g., 'YYYY-MM-DD_Description.pdf', 'Topic-SubTopic_Details.ext', specific use of underscores/spaces/hyphens, capitalization style), **your suggested new name should meticulously follow this established format for consistency.**
        **Incorporate Key Details:** For files like receipts, labels, reports, or notes, embed essential, concise information from the file's summary into the name.
        **Clarity & Cleanliness:** Ensure the suggested name is clear, uses standard characters, avoids excessive or inconsistent punctuation (e.g., multiple consecutive dots or spaces), and is easy to understand at a glance.
        If, after thorough consideration, the current name is already perfect and adheres to any existing patterns, output 'No' for renaming. Otherwise, provide the full `NewName.ext`.

3.  **Reasoning & Confidence:**
    Provide detailed reasoning that justifies your overall plan (the chosen action, subfolder decision, and rename decision), focus on renaming if applicable.
    Provide an overall confidence score (0.0-1.0) for this comprehensive plan.

Output XML, root tag `<final_action>`:
<final_action>
    <reasoning>Detailed reasoning for all decisions.</reasoning>
    <action>move|create_folder_and_move|rename_and_move|move_to_trash|reject_folder</action> 
    <target_folder>{target_path}</target_folder>
    <create_new_folder>Name_or_No_or_NA_for_Trash</create_new_folder>
    <new_file_name>Name_with_ext_or_No_or_NA_for_Trash</new_file_name>
    <confidence>0.X</confidence>
</final_action>"""
        messages = [
            {
                "role": "system",
                "content": "Evaluate file action based on chosen target, with detailed reasoning.",
            },
            {"role": "user", "content": user_prompt_content.strip()},
        ]
        parsed_xml = self._call_llm_and_parse_xml_with_retry(
            messages,
            "final_action",
            max_tokens_for_call=config.MAX_TOKENS_STEP7,
            step_name="Step 7",
        )

        if parsed_xml is None:
            return {
                "action": "error",
                "reasoning": f"LLM final decision failed for {target_path}.",
            }
        decision = {
            key: parsed_xml.findtext(key)
            for key in [
                "action",
                "target_folder",
                "create_new_folder",
                "new_file_name",
                "reasoning",
            ]
        }
        decision["target_folder"] = (
            decision.get("target_folder") or target_path
        )  # Fallback
        decision["confidence"] = float(parsed_xml.findtext("confidence", "0.0"))
        decision["reasoning"] = decision.get("reasoning") or "No reasoning."
        for key in ["create_new_folder", "new_file_name"]:
            if decision[key] and decision[key].strip().lower() in [
                "no",
                "none",
                "na",
                "n/a",
                "na_for_trash",
                "",
            ]:
                decision[key] = None

        self.llm_helper.update_context(
            f"Step 7 Eval: Action {decision['action']}, Conf {decision['confidence']:.2f}. Reason: {decision['reasoning']}"
        )
        print(
            f"LLM final eval: Action={decision['action']}, Conf={decision['confidence']:.2f}, Reason: {decision['reasoning']}"
        )

        if decision["action"] in ["reject_folder", "reject_trash"]:
            return {
                "action": "error",
                "reasoning": f"LLM rejected '{target_path}': {decision['reasoning']}",
            }
        if decision["action"] and decision["action"] not in ["error"]:
            if decision["confidence"] >= config.HIGH_CONFIDENCE:
                return decision
            elif (
                decision["confidence"] >= config.MEDIUM_CONFIDENCE
                and input(
                    f"AI suggests {decision['action']} for '{target_path}' (Conf: {decision['confidence']:.2f}). Proceed? (y/N): "
                ).lower()
                == "y"
            ):
                return decision
            print(f"Action for '{target_path}' declined or low confidence.")
        return {
            "action": "error",
            "reasoning": f"Final action for {target_path} not confirmed.",
        }

    def step8_execute_move(self, decision_details):
        print(f"\n--- Step 8: Executing File Move ---")
        target_path_from_decision = decision_details["target_folder"]
        action = decision_details["action"]
        final_destination_path, is_trash_move_intent = (
            None,
            (
                action == "move_to_trash"
                or target_path_from_decision == config.TRASH_DESTINATION_IDENTIFIER
            ),
        )

        if is_trash_move_intent:
            if not os.path.exists(self.trash_dir):
                try:
                    os.makedirs(self.trash_dir)
                except OSError as e:
                    print(f"Error creating Trash {self.trash_dir}: {e}.")
                    return
            base_name = os.path.basename(self.file_path)
            final_destination_path = os.path.join(self.trash_dir, base_name)
            counter = 1
            temp_base, temp_ext = os.path.splitext(final_destination_path)
            while os.path.exists(final_destination_path):
                final_destination_path = f"{temp_base}_{counter}{temp_ext}"
                counter += 1
            print(
                f"Preparing to move '{self.file_path}' to Trash at '{final_destination_path}'"
            )
        else:
            target_folder_base = target_path_from_decision
            new_subfolder, new_filename = (
                decision_details.get("create_new_folder"),
                decision_details.get("new_file_name"),
            )
            if not target_folder_base:
                print("Error: Target folder undefined.")
                return
            final_target_folder = os.path.normpath(target_folder_base)
            if new_subfolder:
                final_target_folder = os.path.join(final_target_folder, new_subfolder)
                if not os.path.exists(final_target_folder):
                    try:
                        os.makedirs(final_target_folder)
                        print(f"Created subfolder: {final_target_folder}")
                    except OSError as e:
                        print(
                            f"Error creating subfolder {final_target_folder}: {e}. Using base."
                        )
                        final_target_folder = os.path.normpath(target_folder_base)
                elif not os.path.isdir(final_target_folder):
                    print(f"Error: {final_target_folder} not a dir. Using base.")
                    final_target_folder = os.path.normpath(target_folder_base)
            final_basename = (
                new_filename if new_filename else os.path.basename(self.file_path)
            )
            final_destination_path = os.path.normpath(
                os.path.join(final_target_folder, final_basename)
            )

        if os.path.abspath(self.file_path) == os.path.abspath(final_destination_path):
            print(f"File '{self.file_path}' already at target.")
            return
        success, message = file_utils.execute_move(
            self.file_path, final_destination_path, self.trash_dir
        )
        print(message)
        if success and "Successfully moved file to" in message:
            self.file_path = final_destination_path

    def sort_file(self):
        print(f"\n--- Starting Smart Mover for: {self.file_path} ---")
        self.llm_helper.update_context(
            f"Starting sort for '{os.path.basename(self.file_path)}' in '{os.path.dirname(self.file_path)}'."
        )
        parsing_error_occurred_critical_step = False

        action_data = self.step1_initial_decision()
        if not action_data or not action_data.get("action"):
            print("Step 1 failed. Aborting.")
            return
        action, confidence = action_data["action"], action_data["confidence"]
        print(
            f"Step 1 Result: Action='{action}', Conf={confidence:.2f}, Reason: {action_data.get('reasoning')}"
        )

        if action == "stay":
            if (
                confidence >= config.HIGH_CONFIDENCE
                or input(
                    f"AI suggests STAY (Conf: {confidence:.2f}). Confirm? (Y/n): "
                ).lower()
                != "n"
            ):
                print("File will STAY.")
                return
            else:
                action = "more_info"

        if action == "move_to_trash" and confidence >= config.HIGH_CONFIDENCE:
            if (
                input(
                    f"AI strongly suggests Trash for '{os.path.basename(self.file_path)}'. Reason: {action_data.get('reasoning')}. Proceed? (y/N): "
                ).lower()
                == "y"
            ):
                self.step8_execute_move(
                    {
                        "action": "move_to_trash",
                        "target_folder": config.TRASH_DESTINATION_IDENTIFIER,
                    }
                )
                print(f"\n--- File Sort Finished ---")
                return
            else:
                action = "move_to_folder"

        if (
            self.file_summary == "Not yet summarized."
            or action == "more_info"
            or (action == "move_to_folder" and confidence < config.MEDIUM_CONFIDENCE)
        ):
            self.step2_summarize_file()
            print(f"Step 2 Result: Summary='{self.file_summary}'")

        self.step3_suggestion_data = self.step3_get_candidates_and_keywords()
        if not self.step3_suggestion_data:
            print("Step 3 failed. Aborting.")
            parsing_error_occurred_critical_step = True
            if (
                action_data
                and action_data.get("action") == "move_to_trash"
                and input(
                    "Step 3 failed. Initial assessment was Trash. Proceed? (y/N): "
                ).lower()
                == "y"
            ):
                self.step8_execute_move(
                    {
                        "action": "move_to_trash",
                        "target_folder": config.TRASH_DESTINATION_IDENTIFIER,
                    }
                )
            else:
                print("Aborting due to Step 3 failure.")
            return
        print(
            f"Step 3: Folders='{self.step3_suggestion_data.get('folders_str', 'N/A')}' (Conf: {self.step3_suggestion_data.get('folders_confidence', 0):.2f}), FolderKWConf: {self.step3_suggestion_data.get('folder_keywords_confidence', 0):.2f}, FileKWConf: {self.step3_suggestion_data.get('file_keywords_confidence', 0):.2f}"
        )

        initial_paths_str = self.step3_suggestion_data.get("folders_str")
        fs_search_paths, initial_search_includes_trash = [], False
        if initial_paths_str:
            for p_str in initial_paths_str.split(","):
                p_cleaned = p_str.strip()
                if p_cleaned == config.TRASH_DESTINATION_IDENTIFIER:
                    initial_search_includes_trash = True
                elif p_cleaned and os.path.isdir(p_cleaned):
                    fs_search_paths.append(p_cleaned)
                elif p_cleaned:
                    print(f"Warning: Invalid folder '{p_cleaned}' from Step 3.")
        if not fs_search_paths and not initial_search_includes_trash:
            print("Using default search paths.")
            fs_search_paths = [
                os.path.join(self.home_dir, d)
                for d in ["Documents", "Downloads"]
                if os.path.isdir(os.path.join(self.home_dir, d))
            ]  # Simplified default
        if not fs_search_paths and not initial_search_includes_trash:
            print("No valid search paths. Aborting.")
            return

        found_paths_dict_step4 = self.step4_execute_search(
            fs_search_paths,
            self.step3_suggestion_data.get("folder_keywords_str"),
            self.step3_suggestion_data.get("file_keywords_str"),
        )
        ranked_paths_from_step4 = self._score_and_rank_found_paths(
            found_paths_dict_step4
        )
        total_found_paths = len(ranked_paths_from_step4)
        print(f"Step 4: Found {total_found_paths} unique paths, ranked by relevance.")

        processed_paths_for_step6 = []
        paths_were_truncated = False
        paths_to_process_further = ranked_paths_from_step4
        if total_found_paths > config.MAX_PATHS_AFTER_PREFILTER:
            print(
                f"Found {total_found_paths} paths. Truncating to top {config.MAX_PATHS_AFTER_PREFILTER} based on heuristic ranking."
            )
            paths_to_process_further = ranked_paths_from_step4[
                : config.MAX_PATHS_AFTER_PREFILTER
            ]
            paths_were_truncated = True

        for path_str in paths_to_process_further:
            processed_paths_for_step6.append(
                {
                    "path": path_str,
                    "confidence": 0.5,
                    "type": "directory",
                    "source": "heuristic_filter"
                    if paths_were_truncated
                    else "heuristic_ranked_all",
                }
            )
        if initial_search_includes_trash and not any(
            p["path"] == config.TRASH_DESTINATION_IDENTIFIER
            for p in processed_paths_for_step6
        ):  # Ensure trash is an option if initially considered
            processed_paths_for_step6.append(
                {
                    "path": config.TRASH_DESTINATION_IDENTIFIER,
                    "confidence": config.MEDIUM_CONFIDENCE,
                    "type": "trash_bin",
                    "source": "initial_consideration",
                }
            )

        user_provided_hint_for_step6 = None
        final_decision = None
        hint_retries_count = 0
        while hint_retries_count <= config.MAX_HINT_RETRIES:
            target_suggestions = self.step6_process_search_results(
                processed_paths_for_step6,
                paths_were_truncated=paths_were_truncated,
                user_hint_for_prompt=user_provided_hint_for_step6,
            )
            if target_suggestions is None:
                parsing_error_occurred_critical_step = True

            if parsing_error_occurred_critical_step and (not target_suggestions):
                print(
                    "\nWARNING: Critical XML parsing errors with AI folder suggestions."
                )
                if initial_search_includes_trash or (
                    action_data and action_data.get("action") == "move_to_trash"
                ):
                    if input("Fallback to Trash? (y/N): ").lower() == "y":
                        target_suggestions = [
                            {
                                "rank": 1,
                                "confidence": config.MEDIUM_CONFIDENCE,
                                "path": config.TRASH_DESTINATION_IDENTIFIER,
                                "type": "trash_bin",
                                "source": "fallback_parse_error",
                            }
                        ]
                    else:
                        print("User declined Trash fallback. Aborting.")
                        return
                else:
                    print("No clear fallback. Aborting.")
                    return

            if not target_suggestions:
                print("No target suggestions generated (Step 6).")
                if (
                    input(
                        f"AI could not find suitable folder for '{self.file_summary}'. Suggest new? (y/N): "
                    ).lower()
                    == "y"
                ):
                    print("Suggesting new folder not implemented.")
                else:
                    print("Aborting automated sort.")
                return

            print(
                f"Step 6 Result (Hint Attempt {hint_retries_count + 1}): Target suggestions ({len(target_suggestions)}). Top 3: {target_suggestions[:3]}"
            )
            final_decision = self.step7_final_confirmation(
                target_suggestions,
                allow_hint_option=(hint_retries_count < config.MAX_HINT_RETRIES),
            )

            if final_decision and final_decision.get("action") == "user_provided_hint":
                user_provided_hint_for_step6 = final_decision["hint"]
                hint_retries_count += 1
                self.llm_helper.update_context(
                    f"User hint: {user_provided_hint_for_step6}", is_user_hint=True
                )
                print(
                    f"\nUser provided hint. Re-running Step 6 (Attempt {hint_retries_count + 1}/{config.MAX_HINT_RETRIES + 1})."
                )
                parsing_error_occurred_critical_step = False
                continue
            else:
                break

        if (
            not final_decision
            or final_decision.get("action")
            in ["error", "reject_folder", "reject_trash"]
            or not final_decision.get("target_folder")
        ):
            print("Step 7: Final decision rejected or errored. No move performed.")
            if parsing_error_occurred_critical_step:
                print("Reminder: Outcome may be suboptimal due to parsing errors.")
            if (
                action_data
                and action_data.get("action") == "move_to_trash"
                and action_data.get("confidence", 0) >= config.HIGH_CONFIDENCE
            ):
                if (
                    input(
                        "All folder suggestions failed. Initial strong suggestion was Trash. Move to Trash now? (y/N): "
                    ).lower()
                    == "y"
                ):
                    self.step8_execute_move(
                        {
                            "action": "move_to_trash",
                            "target_folder": config.TRASH_DESTINATION_IDENTIFIER,
                        }
                    )
            return

        if (
            parsing_error_occurred_critical_step
            and final_decision.get("action") == "move_to_trash"
        ):
            if (
                input(
                    "CONFIRM: AI folder suggestions lost due to parsing errors. Current suggestion is move to Trash. Proceed? (y/N): "
                ).lower()
                != "y"
            ):
                print("User aborted move to Trash after parsing error warning.")
                return

        print(
            f"Step 7 Result: Action='{final_decision['action']}', Target='{final_decision['target_folder']}', CreateSub='{final_decision.get('create_new_folder')}', NewName='{final_decision.get('new_file_name')}', Conf={final_decision.get('confidence', 0.0):.2f}"
        )
        if (
            final_decision.get("action")
            not in ["error", "reject_folder", "reject_trash"]
            and final_decision.get("confidence", 0.0) >= config.MEDIUM_CONFIDENCE
        ):
            self.step8_execute_move(final_decision)
        else:
            print(
                f"Final decision confidence ({final_decision.get('confidence', 0.0):.2f}) below medium or action not positive. Not performed."
            )
        print(f"\n--- File Sort for: {os.path.basename(self.file_path)} Finished ---")


if __name__ == "__main__":
    config.PYPDF_INSTALLED, config.PILLOW_INSTALLED, config.PDF2IMAGE_INSTALLED = (
        config.check_dependencies()
    )
    parser = argparse.ArgumentParser(description="AI File Sorter - SmartMover")
    parser.add_argument("file_path", help="Path to the file to sort.")
    args = parser.parse_args()
    file_to_sort_arg = args.file_path
    print(f"SmartMover AI starting for: {file_to_sort_arg}")
    try:
        if not os.path.exists(file_to_sort_arg):
            print(f"Error: File '{file_to_sort_arg}' does not exist.")
        elif not os.path.isfile(file_to_sort_arg):
            print(f"Error: Path '{file_to_sort_arg}' is not a file.")
        else:
            SmartMover(file_to_sort_arg).sort_file()
    except Exception as e:
        print(f"Critical error in main execution: {e}")
        import traceback

        traceback.print_exc()
    finally:
        print("\n--- End of Script ---")
