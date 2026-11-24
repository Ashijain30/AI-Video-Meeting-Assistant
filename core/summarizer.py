
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.runnables import RunnableLambda, RunnablePassthrough

import os
import time

def get_llm():
    return ChatGroq(
        model="openai/gpt-oss-120b",
        temperature=0.2,
        api_key=os.getenv("GROQ_API_KEY")
    )


def split_transcript(transcript: str) -> list:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=3000,
        chunk_overlap=200
    )
    return splitter.split_text(transcript)


def safe_invoke(chain, input_data, retries=2):
    """
    Invoke an LLM chain safely.
    Retries temporary rate-limit errors.
    Returns None if all attempts fail.
    """

    for attempt in range(retries + 1):
        try:
            return chain.invoke(input_data)

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
                print(f"LLM request failed: {e}")
                return None


def summarize(transcript: str) -> str:

    if not transcript or not transcript.strip():
        return "No transcript available for summarization."

    try:
        llm = get_llm()

        map_prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "Summarize this portion of a transcript concisely. "
                "Preserve important information, technical details, "
                "decisions, and key points."
            ),
            ("human", "{text}"),
        ])

        map_chain = map_prompt | llm | StrOutputParser()

        chunks = split_transcript(transcript)
        chunk_summaries = []

        for i, chunk in enumerate(chunks, 1):

            print(f"Summarizing chunk {i}/{len(chunks)}...")

            summary = safe_invoke(map_chain, {"text": chunk})

            if summary:
                chunk_summaries.append(summary)

            else:
                # Fallback: retain original chunk if LLM fails
                print(f"Using fallback for summary chunk {i}")
                chunk_summaries.append(chunk[:1000])

        combined = "\n\n".join(chunk_summaries)

        combined_prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "You are an expert summarizer. Combine the following "
                "partial summaries into one clear, professional summary "
                "using bullet points. Avoid repetition."
            ),
            ("human", "{text}"),
        ])

        combined_chain = combined_prompt | llm | StrOutputParser()

        final_summary = safe_invoke(
            combined_chain,
            {"text": combined}
        )

        if final_summary:
            return final_summary

        # Final fallback if summary API fails
        return combined[:5000]

    except Exception as e:
        print(f"Summarization error: {e}")

        # Absolute fallback
        return transcript[:3000]


def generate_title(transcript: str) -> str:

    if not transcript or not transcript.strip():
        return "Untitled Video"

    try:
        llm = get_llm()

        title_prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "Based on the transcript, generate a short professional "
                "title of maximum 8 words. Return only the title."
            ),
            ("human", "{text}"),
        ])

        title_chain = title_prompt | llm | StrOutputParser()

        title = safe_invoke(
            title_chain,
            {"text": transcript[:2000]}
        )

        if title:
            return title.strip().strip('"')

    except Exception as e:
        print(f"Title generation error: {e}")

    # Fallback title
    words = transcript.split()[:8]

    if words:
        return " ".join(words).strip(".,!?")

    return "Video Analysis"
