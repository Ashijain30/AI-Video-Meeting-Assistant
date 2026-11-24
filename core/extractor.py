from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

import os
import time


def get_llm():
    return ChatGroq(
        model="openai/gpt-oss-120b",
        temperature=0.2,
        api_key=os.getenv("GROQ_API_KEY")
    )


def safe_invoke(chain, transcript, retries=2):

    for attempt in range(retries + 1):

        try:
            return chain.invoke({"text": transcript})

        except Exception as e:

            error_message = str(e).lower()

            is_rate_limit = (
                "429" in error_message
                or "rate limit" in error_message
                or "rate_limited" in error_message
            )

            if is_rate_limit and attempt < retries:

                wait_time = 2 ** (attempt + 1)

                print(
                    f"Rate limit encountered. "
                    f"Retrying in {wait_time} seconds..."
                )

                time.sleep(wait_time)

            else:
                print(f"Extraction failed: {e}")
                return None


def build_chain(system_prompt: str):

    llm = get_llm()

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{text}"),
    ])

    return prompt | llm | StrOutputParser()


def extract_action_items(transcript: str) -> str:

    if not transcript:
        return "No action items found."

    try:

        chain = build_chain(
            "You are an expert meeting analyst. Extract all action items "
            "from the transcript.\n\n"
            "For each action item provide:\n"
            "- Task description\n"
            "- Owner, if mentioned\n"
            "- Deadline, if mentioned; otherwise write 'Not specified'\n\n"
            "Format as a numbered list. If no action items exist, "
            "say 'No action items found.'"
        )

        result = safe_invoke(chain, transcript)

        if result:
            return result

    except Exception as e:
        print(f"Action item extraction error: {e}")

    return "Action item extraction unavailable due to AI API error."


def extract_key_decisions(transcript: str) -> str:

    if not transcript:
        return "No key decisions found."

    try:

        chain = build_chain(
            "You are an expert meeting analyst. Extract all key decisions "
            "made in the transcript. Format them as a numbered list. "
            "If there are no decisions, say 'No key decisions found.'"
        )

        result = safe_invoke(chain, transcript)

        if result:
            return result

    except Exception as e:
        print(f"Decision extraction error: {e}")

    return "Decision extraction unavailable due to AI API error."


def extract_questions(transcript: str) -> str:

    if not transcript:
        return "No open questions found."

    try:

        chain = build_chain(
            "Extract unresolved questions, unanswered issues, and topics "
            "requiring follow-up from the transcript. Format as a numbered "
            "list. If there are no questions, say 'No open questions found.'"
        )

        result = safe_invoke(chain, transcript)

        if result:
            return result

    except Exception as e:
        print(f"Question extraction error: {e}")

    return "Question extraction unavailable due to AI API error."
