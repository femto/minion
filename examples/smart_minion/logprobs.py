import os

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

# Load the .env file
load_dotenv()

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", "<your OpenAI API key if not set as env var>"))


def get_completion(
    messages: list[dict[str, str]],
    model: str = "deepseek-coder",
    max_tokens=500,
    temperature=0.0,
    stop=None,
    seed=123,
    tools=None,
    logprobs=None,  # whether to return log probabilities of the output tokens or not. If true, returns the log probabilities of each output token returned in the content of message..
    top_logprobs=None,
) -> str:
    params = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stop": stop,
        "seed": seed,
        "logprobs": logprobs,
        "top_logprobs": top_logprobs,
    }
    if tools:
        params["tools"] = tools

    completion = client.chat.completions.create(**params)
    return completion


CLASSIFICATION_PROMPT = """You will be given a headline of a news article.
Classify the article into one of the following categories: Technology, Politics, Sports, and Art.
Return only the name of the category, and nothing else.
MAKE SURE your output is one of the four categories stated.
Article headline: {headline}"""
headlines = [
    "Tech Giant Unveils Latest Smartphone Model with Advanced Photo-Editing Features.",
    "Local Mayor Launches Initiative to Enhance Urban Public Transport.",
    "Tennis Champion Showcases Hidden Talents in Symphony Orchestra Debut",
]
# for headline in headlines:
#     print(f"\nHeadline: {headline}")
#     API_RESPONSE = get_completion(
#         [{"role": "user", "content": CLASSIFICATION_PROMPT.format(headline=headline)}],
#         model="deepseek-coder",
#         #model="gpt-4o",
#         logprobs=True,
#         top_logprobs=2,
#     )
#     top_two_logprobs = API_RESPONSE.choices[0].logprobs.content[0].top_logprobs
#     html_content = ""
#     for i, logprob in enumerate(top_two_logprobs, start=1):
#         html_content += (
#             f"<span style='color: cyan'>Output token {i}:</span> {logprob.token}, "
#             f"<span style='color: darkorange'>logprobs:</span> {logprob.logprob}, "
#             f"<span style='color: magenta'>linear probability:</span> {np.round(np.exp(logprob.logprob)*100,2)}%<br>"
#         )
#     display(HTML(html_content))
#     print("\n")
# Article retrieved
# ada_lovelace_article = """Augusta Ada King, Countess of Lovelace (née Byron; 10 December 1815 – 27 November 1852) was an English mathematician and writer, chiefly known for her work on Charles Babbage's proposed mechanical general-purpose computer, the Analytical Engine. She was the first to recognise that the machine had applications beyond pure calculation.
# Ada Byron was the only legitimate child of poet Lord Byron and reformer Lady Byron. All Lovelace's half-siblings, Lord Byron's other children, were born out of wedlock to other women. Byron separated from his wife a month after Ada was born and left England forever. He died in Greece when Ada was eight. Her mother was anxious about her upbringing and promoted Ada's interest in mathematics and logic in an effort to prevent her from developing her father's perceived insanity. Despite this, Ada remained interested in him, naming her two sons Byron and Gordon. Upon her death, she was buried next to him at her request. Although often ill in her childhood, Ada pursued her studies assiduously. She married William King in 1835. King was made Earl of Lovelace in 1838, Ada thereby becoming Countess of Lovelace.
# Her educational and social exploits brought her into contact with scientists such as Andrew Crosse, Charles Babbage, Sir David Brewster, Charles Wheatstone, Michael Faraday, and the author Charles Dickens, contacts which she used to further her education. Ada described her approach as "poetical science" and herself as an "Analyst (& Metaphysician)".
# When she was eighteen, her mathematical talents led her to a long working relationship and friendship with fellow British mathematician Charles Babbage, who is known as "the father of computers". She was in particular interested in Babbage's work on the Analytical Engine. Lovelace first met him in June 1833, through their mutual friend, and her private tutor, Mary Somerville.
# Between 1842 and 1843, Ada translated an article by the military engineer Luigi Menabrea (later Prime Minister of Italy) about the Analytical Engine, supplementing it with an elaborate set of seven notes, simply called "Notes".
# Lovelace's notes are important in the early history of computers, especially since the seventh one contained what many consider to be the first computer program—that is, an algorithm designed to be carried out by a machine. Other historians reject this perspective and point out that Babbage's personal notes from the years 1836/1837 contain the first programs for the engine. She also developed a vision of the capability of computers to go beyond mere calculating or number-crunching, while many others, including Babbage himself, focused only on those capabilities. Her mindset of "poetical science" led her to ask questions about the Analytical Engine (as shown in her notes) examining how individuals and society relate to technology as a collaborative tool.
# """
#
# # Questions that can be easily answered given the article
# easy_questions = [
#     "What nationality was Ada Lovelace?",
#     "What was an important finding from Lovelace's seventh note?",
# ]
#
# # Questions that are not fully covered in the article
# medium_questions = [
#     "Did Lovelace collaborate with Charles Dickens",
#     "What concepts did Lovelace build with Charles Babbage",
# ]
#
# PROMPT = """You retrieved this article: {article}. The question is: {question}.
# Before even answering the question, consider whether you have sufficient information in the article to answer the question fully.
# Your output should JUST be the boolean true or false, of if you have sufficient information in the article to answer the question.
# Respond with just one word, the boolean true or false. You must output the word 'True', or the word 'False', nothing else.
# """
#
# html_output = ""
# html_output += "Questions clearly answered in article"
#
# for question in easy_questions:
#     API_RESPONSE = get_completion(
#         [
#             {
#                 "role": "user",
#                 "content": PROMPT.format(
#                     article=ada_lovelace_article, question=question
#                 ),
#             }
#         ],
#         model="gpt-4o",
#         logprobs=True,
#     )
#     html_output += f'<p style="color:green">Question: {question}</p>'
#     for logprob in API_RESPONSE.choices[0].logprobs.content:
#         html_output += f'<p style="color:cyan">has_sufficient_context_for_answer: {logprob.token}, <span style="color:darkorange">logprobs: {logprob.logprob}, <span style="color:magenta">linear probability: {np.round(np.exp(logprob.logprob)*100,2)}%</span></p>'
#
# html_output += "Questions only partially covered in the article"
#
# for question in medium_questions:
#     API_RESPONSE = get_completion(
#         [
#             {
#                 "role": "user",
#                 "content": PROMPT.format(
#                     article=ada_lovelace_article, question=question
#                 ),
#             }
#         ],
#         model="gpt-4o",
#         logprobs=True,
#         top_logprobs=3,
#     )
#     html_output += f'<p style="color:green">Question: {question}</p>'
#     for logprob in API_RESPONSE.choices[0].logprobs.content:
#         html_output += f'<p style="color:cyan">has_sufficient_context_for_answer: {logprob.token}, <span style="color:darkorange">logprobs: {logprob.logprob}, <span style="color:magenta">linear probability: {np.round(np.exp(logprob.logprob)*100,2)}%</span></p>'
#
# display(HTML(html_output))
# sentence_list = [
#     "My",
#     "My least",
#     "My least favorite",
#     "My least favorite TV",
#     "My least favorite TV show",
#     "My least favorite TV show is",
#     "My least favorite TV show is Breaking Bad",
# ]
#
# high_prob_completions = {}
# low_prob_completions = {}
# html_output = ""
#
# for sentence in sentence_list:
#     PROMPT = """Complete this sentence. You are acting as auto-complete. Simply complete the sentence to the best of your ability, make sure it is just ONE sentence: {sentence}"""
#     API_RESPONSE = get_completion(
#         [{"role": "user", "content": PROMPT.format(sentence=sentence)}],
#         model="gpt-4o",
#         logprobs=True,
#         top_logprobs=3,
#     )
#     html_output += f'<p>Sentence: {sentence}</p>'
#     first_token = True
#     for token in API_RESPONSE.choices[0].logprobs.content[0].top_logprobs:
#         html_output += f'<p style="color:cyan">Predicted next token: {token.token}, <span style="color:darkorange">logprobs: {token.logprob}, <span style="color:magenta">linear probability: {np.round(np.exp(token.logprob)*100,2)}%</span></p>'
#         if first_token:
#             if np.exp(token.logprob) > 0.95:
#                 high_prob_completions[sentence] = token.token
#             if np.exp(token.logprob) < 0.60:
#                 low_prob_completions[sentence] = token.token
#         first_token = False
#     html_output += "<br>"
#
# display(HTML(html_output))


# PROMPT = """What's the longest word in the English language?"""
#
# API_RESPONSE = get_completion(
#     [{"role": "user", "content": PROMPT}], model="deepseek-coder", logprobs=True, top_logprobs=5
# )


# def highlight_text(api_response):
#     colors = [
#         "#FF00FF",  # Magenta
#         "#008000",  # Green
#         "#FF8C00",  # Dark Orange
#         "#FF0000",  # Red
#         "#0000FF",  # Blue
#     ]
#     tokens = api_response.choices[0].logprobs.content
#
#     color_idx = 0  # Initialize color index
#     html_output = ""  # Initialize HTML output
#     for t in tokens:
#         token_str = bytes(t.bytes).decode("utf-8")  # Decode bytes to string
#
#         # Add colored token to HTML output
#         html_output += f"<span style='color: {colors[color_idx]}'>{token_str}</span>"
#
#         # Move to the next color
#         color_idx = (color_idx + 1) % len(colors)
#     display(HTML(html_output))  # Display HTML output
#     print(f"Total number of tokens: {len(tokens)}")
#
# # highlight_text(API_RESPONSE)
#
# PROMPT = """Output the blue heart emoji and its name."""
# API_RESPONSE = get_completion(
#     [{"role": "user", "content": PROMPT}], model="deepseek-coder", logprobs=True
# )
#
# aggregated_bytes = []
# joint_logprob = 0.0
#
# # Iterate over tokens, aggregate bytes and calculate joint logprob
# for token in API_RESPONSE.choices[0].logprobs.content:
#     print("Token:", token.token)
#     print("Log prob:", token.logprob)
#     print("Linear prob:", np.round(exp(token.logprob) * 100, 2), "%")
#     print("Bytes:", token.bytes, "\n")
#     aggregated_bytes += token.bytes
#     joint_logprob += token.logprob
#
# # Decode the aggregated bytes to text
# aggregated_text = bytes(aggregated_bytes).decode("utf-8")
#
# # Assert that the decoded text is the same as the message content
# assert API_RESPONSE.choices[0].message.content == aggregated_text
#
# # Print the results
# print("Bytes array:", aggregated_bytes)
# print(f"Decoded bytes: {aggregated_text}")
# print("Joint prob:", np.round(exp(joint_logprob) * 100, 2), "%")
# 3

prompts = [
    "In a short sentence, has artifical intelligence grown in the last decade?",
    "In a short sentence, what are your thoughts on the future of artificial intelligence?",
]

for prompt in prompts:
    API_RESPONSE = get_completion(
        [{"role": "user", "content": prompt}],
        model="deepseek-coder",
        logprobs=True,
    )

    logprobs = [token.logprob for token in API_RESPONSE.choices[0].logprobs.content]
    response_text = API_RESPONSE.choices[0].message.content
    response_text_tokens = [token.token for token in API_RESPONSE.choices[0].logprobs.content]
    max_starter_length = max(len(s) for s in ["Prompt:", "Response:", "Tokens:", "Logprobs:", "Perplexity:"])
    max_token_length = max(len(s) for s in response_text_tokens)

    formatted_response_tokens = [s.rjust(max_token_length) for s in response_text_tokens]
    formatted_lps = [f"{lp:.2f}".rjust(max_token_length) for lp in logprobs]

    perplexity_score = np.exp(-np.mean(logprobs))
    print("Prompt:".ljust(max_starter_length), prompt)
    print("Response:".ljust(max_starter_length), response_text, "\n")
    print("Tokens:".ljust(max_starter_length), " ".join(formatted_response_tokens))
    print("Logprobs:".ljust(max_starter_length), " ".join(formatted_lps))
    print("Perplexity:".ljust(max_starter_length), perplexity_score, "\n")
