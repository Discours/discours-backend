import re
import nltk
from bs4 import BeautifulSoup
from nltk.corpus import stopwords
from pymystem3 import Mystem
from string import punctuation
from transformers import BertTokenizer

nltk.download("stopwords")


def get_clear_text(text):
    soup = BeautifulSoup(text, 'html.parser')

    # extract the plain text from the HTML document without tags
    clear_text = ''
    for tag in soup.find_all():
        clear_text += tag.string or ''

    clear_text = re.sub(pattern='[\u202F\u00A0\n]+', repl=' ', string=clear_text)

    # only words
    clear_text = re.sub(pattern='[^A-ZА-ЯЁ -]', repl='', string=clear_text, flags=re.IGNORECASE)

    clear_text = re.sub(pattern='\s+', repl=' ', string=clear_text)

    clear_text = clear_text.lower()

    mystem = Mystem()
    russian_stopwords = stopwords.words("russian")

    tokens = mystem.lemmatize(clear_text)
    tokens = [token for token in tokens if token not in russian_stopwords \
              and token != " " \
              and token.strip() not in punctuation]

    clear_text = " ".join(tokens)

    return clear_text


# if __name__ == '__main__':
#
#     # initialize the tokenizer with the pre-trained BERT model and vocabulary
#     tokenizer = BertTokenizer.from_pretrained('bert-base-multilingual-cased')
#
#     # split each text into smaller segments of maximum length 512
#     max_length = 512
#     segmented_texts = []
#     for text in [clear_text1, clear_text2]:
#         segmented_text = []
#         for i in range(0, len(text), max_length):
#             segment = text[i:i+max_length]
#             segmented_text.append(segment)
#         segmented_texts.append(segmented_text)
#
#     # tokenize each segment using the BERT tokenizer
#     tokenized_texts = []
#     for segmented_text in segmented_texts:
#         tokenized_text = []
#         for segment in segmented_text:
#             segment_tokens = tokenizer.tokenize(segment)
#             segment_tokens = ['[CLS]'] + segment_tokens + ['[SEP]']
#             tokenized_text.append(segment_tokens)
#         tokenized_texts.append(tokenized_text)
#
#     input_ids = []
#     for tokenized_text in tokenized_texts:
#         input_id = []
#         for segment_tokens in tokenized_text:
#             segment_id = tokenizer.convert_tokens_to_ids(segment_tokens)
#             input_id.append(segment_id)
#         input_ids.append(input_id)
#
#     print(input_ids)
