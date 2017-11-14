# This script contains all the help function related to pre-trained word vector and deal with different data loader
from sklearn.feature_extraction import stop_words
import torch
from torch.utils.data import Dataset
from collections import Counter
from tqdm import tqdm
import pandas as pd
import string
import numpy as np
translator = str.maketrans('', '', string.punctuation)


class ParaphraseData:
    """
    Class that represents a train/validation/test data
    """

    def __init__(self, raw_text, label):
        """
        :param raw_text: Save the raw text into tuple format
        :param label: The label of the paraphrases
        """
        self.raw_text = raw_text
        self.label = label

    def set_ngram(self, ngrams_a, ngrams_b):
        self.ngrams_a = ngrams_a
        self.ngrams_b = ngrams_b

    # TODO: Need to think about here
    def set_ngrams_idx(self, ngrams_idx_a, ngrams_idx_b):
        self.ngrams_idx_a = ngrams_idx_a
        self.ngrams_idx_b = ngrams_idx_b


class ParaphraseDataset(Dataset):
    """
    Class that represents a train/validation/test dataset that's readable for PyTorch
    Note that this class inherits torch.utils.data.Dataset
    """
    def __init__(self, preprocessed_dataset):
        self.data = preprocessed_dataset

    def __len__(self):
        return len(self.data)

    def __getitem__(self, key):
        return (self.data[key].ngrams_idx_a, self.data[key].ngrams_idx_b), self.data[key].label


def construct_data_set(file_name):
    """
    Function that reads a tsv file into the memory.
    """
    data_set = []
    paraphrase_df = pd.read_csv(file_name, sep='\t', header=None, names=["label", "text_a", "text_b", "id"])
    for index in range(len(paraphrase_df)):
        label = paraphrase_df.iloc[index, :]['label']
        text_a = paraphrase_df.iloc[index, :]['text_a']
        text_b = paraphrase_df.iloc[index, :]['text_b']
        text = (text_a, text_b)
        paraphrase_data = ParaphraseData(raw_text=text, label=label)
        data_set.append(paraphrase_data)
    return data_set


def preprocess_text(text):
    """
    :param text: A sentence that has not been preprocessed
    :return: A preprocessed sentence
    """
    text = text.translate(translator).lower()
    return text


def get_overlap_phrases(window_size, text):
    """
    :param window_size: The window size to extract the context
    :param text: the raw sentence
    :return: a list of overlapping phrases
    """
    phrases_list = []
    word_list = text.split()
    sentence_length = len(word_list)
    for word_offset in range(sentence_length):
        index = [i for i in range(word_offset - window_size, word_offset + window_size + 1) if
                 i >= 0 and i < sentence_length]
        phrases_list.append([word_list[ind] for ind in index])
    return phrases_list


def extract_phrases_from_text(text, window_size):
    """
    Extract overlap phrases from sentence
    :param text: The tuple of two sentences in the dataset
    :param window_size: The context window size that you want to use
    :return: A list of overlap phrases
    """
    text_a, text_b = text[0], text[1]
    phrases_a = get_overlap_phrases(window_size, text_a)
    phrases_b = get_overlap_phrases(window_size, text_b)
    return phrases_a, phrases_b


def extract_ngram_from_phrases(phrases, n):
    """
    :param phrases:
    :return: A list of character level n-gram extract from phrases
    """
    phrases_ngram_list = []
    for phrase in phrases:
        word_ngram_list = []
        for word in phrase:
            padded_word = "[" + word + "]"
            if len(padded_word) < n:
                word_ngram_list.append(tuple(list(padded_word)))
            char_ngrams = list(zip(*[padded_word[i:] for i in range(n)]))
            if char_ngrams:
                word_ngram_list.append(char_ngrams[0])
            word_ngram_list.append(char_ngrams)
            phrases_ngram_list.append(word_ngram_list)
    return phrases_ngram_list


def extract_ngram_from_text(text, window_size, n):
    """
    Extract character level n-gram from overlap phrases (a_hat or b_hat)
    :param phrases: A over which we want to extract character-level n_gram from
    :param n: n is the number of  character-level grams that you want to extract from text
    :param remove_stopwords: TODO: delete it or not
    :return:
    """
    phrases_a, phrases_b = extract_phrases_from_text(text, window_size)
    phrases_ngrams_a = extract_ngram_from_phrases(phrases_a, n)
    phrases_ngrams_b = extract_ngram_from_phrases(phrases_b, n)
    return phrases_ngrams_a, phrases_ngrams_b


def phrases_ngrams_to_index(phrases_ngrams_list, ngram_indexer):
    """
    :param phrases_ngrams_list: a phrases ngrams list derived from a sentence
    :param ngram_indexer: A pre-trained char-ngram indexer
    :return:
    """
    # Please DO NOT assign any ngram to index 0 which is reserved for PAD token
    index_list = [[ngram_indexer[token] for token in phrases_ngrams if token in ngram_indexer]
                  for phrases_ngrams in phrases_ngrams_list]
    return index_list


def process_text_dataset(dataset, window_size, n, topk=None, ngram_indexer=None):
    """
    Top level function that encodes each datum into a list of ngram indices
    @param dataset: list of IMDBDatum
    @param n: n in "n-gram" (character_level)
    @param topk: #
    @param ngram_indexer: a dictionary that maps ngram to an unique index
    """
    # extract n-gram
    for i in tqdm(range(len(dataset))):
        text = dataset[i].raw_text
        ngrams_a, ngrams_b = extract_ngram_from_text(text, window_size, n)
        dataset[i].set_ngram(ngrams_a=ngrams_a, ngrams_b=ngrams_b)
    # select top k ngram
    # TODO: Get pre-trained ngram indexer here
    # if ngram_indexer is None:
    #     ngram_indexer = construct_ngram_indexer([datum.ngram for datum in dataset], topk)
    # vectorize each datum
    for i in range(len(dataset)):
        dataset[i].set_ngrams_idx(ngrams_idx_a=phrases_ngrams_to_index(dataset[i].ngrams_a, ngram_indexer),
                                  ngrams_idx_b=phrases_ngrams_to_index(dataset[i].ngrams_b, ngram_indexer))
    return dataset, ngram_indexer




def construct_data_loader(processed_data, batch_size, shuffle=True):
    data_loader = torch.utils.data.DataLoader(dataset=processed_data,
                                              batch_size=batch_size,
                                              shuffle=shuffle)
    return data_loader


#######
#TODO: Get pre-trained ngram indexer here
def construct_ngram_indexer(ngram_counter_list, topk):
    """
    Function that selects the most common topk ngrams
    @param ngram_counter_list: list of counters
    @param topk: # of
    @return ngram2idx: a dictionary that maps ngram to an unique index
    """
    # find the top k ngram
    # maps the ngram to an unique index
    ngram_counter = Counter()
    for counter in tqdm(ngram_counter_list):
        ngram_counter.update(counter)
    ngram_counter_topk = ngram_counter.most_common(topk)
    ngram_indexer = {ngram_counter_topk[index][0]: index + 1 for index in range(len(ngram_counter_topk))}
    return ngram_indexer


#TODO: To decide if we need a collate function
def collate_func(batch):
    """
    Customized function for DataLoader that dynamically pads the batch so that all
    data have the same length
    """
    data_list = []
    label_list = []
    length_list = []
    for datum in batch:
        label_list.append(datum[1])
        length_list.append(datum[0][1])
    max_length = np.max(length_list)
    # padding
    for datum in batch:
        padded_vec = np.pad(np.array(datum[0][0]),
                            pad_width=(0, max_length-datum[0][1]),
                            mode="constant", constant_values=0)
        data_list.append(padded_vec)
    return [torch.from_numpy(np.array(data_list)), torch.LongTensor(length_list), torch.LongTensor(label_list)]





# TODO: To decide if we need to use h5py format to save the data.

# train_set = construct_data_set("train_dir")
# train_data, train_ngram_indexer = process_text_dataset(train_set, args.n_gram, args.vocab_size)
# processed_train_data = ParaphraseDataset(train_data)
# train_data_loader = construct_data_loader(processed_train_data, size)
