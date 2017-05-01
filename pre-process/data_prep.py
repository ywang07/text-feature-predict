"""
prepare crawled data for feature extraction
take both json and text file as input
extract date and textual article
"""

import ast # abstract syntax trees
import os
import numpy as np
import pandas as pd
from collections import defaultdict
import nltk
from nltk.tokenize import word_tokenize
from operator import itemgetter
import cPickle as pkl

from clean_str import clean_str

def extract_docs(path_in, path_out):
    """
    extract (and merge) all crawled documents in the given path
    :param path_in: path to crawled docs
    :param path_out: path to output extracted docs
    """
    files = os.listdir(path_in)
    try:
        os.stat(path_out)
    except:
        os.mkdir(path_out)

    f_json = defaultdict(list)
    f_text = defaultdict(list)
    companies = []

    for f in files:
        if "json" in f:
            company = f.split("-json")[0].split("_")[-1]
            f_json[company].append(f)
            companies.append(company)
        elif "text" in f:
            company = f.split("-text")[0].split("_")[-1]
            f_text[company].append(f)
        else:
            print "unrecognized file:", f
    companies = list(set(companies))

    for company in companies:
        print "processing", company
        doc_info = []
        doc_contents = []
        # load all the lines with meaningful doc_info
        for f in f_json[company]:
            document_json = open(path_in + f, "r")
            for line in document_json.readlines():
                l = ast.literal_eval(line)['response']['docs']
                if len(l) > 0:
                    for ll in l:
                        ll["pub_date"] = ll["pub_date"].split("T")[0]
                    doc_info.append(l)
        # load all the articles
        for f in f_text[company]:
            document_contents = open(path_in + f, "r")
            for line in document_contents.readlines():
                split = line.split('\t')
                if len(split) == 3:  # TODO: Bug in parsing
                    doc_contents.append((split[0], split[2].replace('\n', '')))

        extract_doc_compary(doc_info=doc_info,
                            doc_contents=doc_contents,
                            f_output=path_out+company+".tsv")

def extract_doc_compary(doc_info, doc_contents, f_output):
    """
    extract date and actual textual articles from raw corpus
    :param doc_info: doc info loaded from json file
    :param doc_contents: actual doc articles from text file
    :param f_output: path to output file, each line: date /t [a list of articles]
    """
    document_output = open(f_output, "w")

    # Create DataFrame that contains all attributes
    doc_attributes = pd.DataFrame()
    for doc in doc_info:
        doc_attributes = doc_attributes.append(pd.DataFrame.from_dict(doc))
    doc_attributes = doc_attributes.reset_index(drop=True)
    doc_attributes = doc_attributes.drop_duplicates(subset='_id') # remove duplicate rows w.r.t. label "_id"

    # Create DataFrame that contains docId and document content
    contents = pd.DataFrame(doc_contents, columns=['_id', 'text'])
    contents = contents.drop_duplicates()

    # Join table of attributes with document content table
    collection = doc_attributes.merge(contents, left_on="_id", right_on="_id")
    # collection[['_id', 'pub_date', 'text']]
    # print collection

    # concatenate documents
    select = collection[['pub_date', 'text']]
    concat = select.groupby('pub_date')
    concat = concat['text'].apply(list)
    # print concat

    # write to output file
    concat.to_csv(document_output, sep='\t', encoding='utf8')

    document_output.close()

class lda_prep:
    def __init__(self, path_in, path_out, vocab_size=50000, stop_words=False, load_collection=False):
        self.path_in = path_in
        self.path_out = path_out
        self.stop_words = stop_words
        self.vocab_size = vocab_size

        self.wordList = defaultdict(int) # word -> freq
        self.vocab = dict()
        self.total_words_cnt = 0.
        self.collections = [] # [company, date, list of document words]

        try:
            os.stat(self.path_out)
        except:
            os.mkdir(self.path_out)

        self.fout = open(self.path_out + "corpus_lda.txt", "w")  # doc-term format input for lda

        if not load_collection:
            self.fin_names = os.listdir(self.path_in)


            for fin_name in self.fin_names:
                self.load_docs(fin_name=fin_name)
        else:
            self.load_collection(path_in)

        print "collection size:", len(self.collections)

        self.prep_vocab()

        #self.prep_doc_term()

    def load_docs(self, fin_name):
        """
        load documents for different companies
        :param fin_name: input file name
               the file is of the same format as output of extract_doc_company()
        """
        print "loading documents from ",
        with open(self.path_in+fin_name, "r") as f:
            lines = f.readlines()
        company_name = fin_name.replace(".tsv", "").split("-")[-1]
        print company_name, "...",

        for line in lines:
            line = line.strip().split("\t") # date, doc_content
            content = clean_str(line[1])
            if len(content) == 0:
                continue
            tokens = nltk.word_tokenize(content.decode('utf-8')) # tokenize
            for token in tokens:
                self.wordList[token] += 1
            self.total_words_cnt += len(tokens)
            self.collections.append([company_name, line[0], tokens])
        print "done! corpus size:", len(lines), "total word count:", self.total_words_cnt

    def load_collection(self, fin_name):
        """
        load documents from a document collection [company_name, date, document]
        the document content in the collection needs to be pre-processed and tokenized
        with a space delimiter
        :param fin_name: the path to the document collection
        """
        print "loading documents from corpus: {}".format(fin_name)
        for line in open(fin_name):
            line = line.strip().split("\t")  # company_name, date, doc_content
            company_name = line[0]
            date = line[1]
            content = line[2]
            if len(content) == 0:
                continue
            tokens = content.split(' ')
            for token in tokens:
                self.wordList[token] += 1
            self.total_words_cnt += len(tokens)
            self.collections.append([company_name, date, tokens])
        print "done! corpus size:", len(self.collections), "total word count:", self.total_words_cnt

    def prep_vocab(self):
        """
        generate vocab (generate index based on word frequency)
        dump vocab to file
        """
        print "generating vocabulary ...",
        self.wordList = self.wordList.items()
        self.wordList = sorted(self.wordList, key=itemgetter(1), reverse=True)

        freq_cov = 0.
        for i in range(min(self.vocab_size, len(self.wordList))):
            self.vocab[self.wordList[i][0]] = i
            freq_cov += self.wordList[i][1]

        with open(self.path_out + "vocab.txt", "w") as f:
            f.writelines(["%s\n" % word[0] for word in self.wordList[:len(self.vocab)]])
        with open(self.path_out + "vocab.pkl", "wb") as f:
            pkl.dump(self.vocab, f)
        print "done!"
        print "unique words:", len(self.wordList)
        print "vocab size:", len(self.vocab)
        print "frequency converage:", float(freq_cov) / self.total_words_cnt

    def comb_docs(self, fout_name='corpus_raw.txt'):
        print "combing docs for different companies ...",
        fout = open(self.path_out+fout_name, "w")
        for doc in self.collections:
            s = doc[0] + "\t" + doc[1] + "\t"
            for word in doc[-1]:
                if word in self.vocab:
                    s += word + " "
            fout.write(s+"\n")
        fout.close()
        print "done!"

    def prep_doc_term(self):
        """
        generate doc-term format file as LDA input
        each line: {#unique_words} {widx:freq}, space separated
        """
        print "preparing doc-term matrix for LDA ...",
        for doc in self.collections:
            content = []
            for word in doc[-1]:
                if word in self.vocab:
                    content.append(self.vocab[word])
            word_freq = defaultdict(int)
            for widx in content:
                word_freq[widx] += 1
            s = str(len(word_freq)) + " "
            for kk, vv in word_freq.iteritems():
                s += str(kk) + ":" + str(vv) + " "
            self.fout.write(s+"\n")
        self.fout.close()
        print "done!"

class DataPoints:
    def __init__(self):
        self.x_doc = []
        self.x_stock = []
        self.x_lda = []
        self.y = []

    def set(self, data):
        self.x_doc = data[0]
        self.y = data[-1]
        if len(data) == 3:
            self.set_stock(data[1])

    def set_doc(self, x_doc):
        self.x_doc = x_doc

    def set_lda(self, x_lda):
        self.x_lda = np.array(x_lda)

    def set_stock(self, x_stock):
        self.x_stock = np.array(x_stock)

    def set_y(self, y):
        self.y = y

    def clear(self):
        self.x_doc = []
        self.x_stock = []
        self.x_lda = []
        self.y = []

class DataProcessor:
    def __init__(self, vocab_size=None, valid_portion=None, overwrite=False, shuffle=True):
        self.train = DataPoints()
        self.valid = DataPoints()
        self.test = DataPoints()
        self.vocab = dict() # vocab for the loaded dataset
        self.vocab_size = vocab_size # take top vocab_size vocab for loaded dataset if not None
        self.overwrite = overwrite
        self.use_shuffle = shuffle
        self.sidx_train = [] # shuffled idx list for training set
        self.sidx_test = []

    def run_docs(self, f_corpus, f_meta_data, f_dataset_out, f_vocab=None):
        def _run():
            self.load_data(f_corpus, f_meta_data, shuffle=True)
            self.gen_vocab(f_vocab=f_vocab)
            self.save_data(f_dataset_out=f_dataset_out)

        try:
            os.stat(f_dataset_out)
            print f_dataset_out + " already exist!"
            if self.overwrite:
                print "overwriting ..."
                _run()
        except:
            _run()

    def run_lda(self, dir_lda, f_meta_data, f_lda_out):
        train_idx, test_idx = self.load_metadata(f_meta_data)
        lda_data = []

        paths = os.listdir(dir_lda)
        for path_lda in paths:
            topic_dist = self.load_lda(dir_lda + path_lda)
            if len(topic_dist) == 0:
                continue
            lda_train = [topic_dist[idx] for idx in train_idx]
            lda_test = [topic_dist[idx] for idx in test_idx]

            if self.use_shuffle:
                lda_train = [lda_train[idx] for idx in self.sidx_train]
                lda_test = [lda_test[idx] for idx in self.sidx_test]

            lda_data.append([np.array(lda_train), np.array(lda_test)])

        with open(f_lda_out, "wb") as f:
            pkl.dump(lda_data, f)
        print "number of different topic features: {}".format(len(lda_data))


    def load_metadata(self, f_meta_data):
        train_idx = []
        test_idx = []

        with open(f_meta_data, "r") as f:
            meta_data = f.readlines()
        for lidx, meta_line in enumerate(meta_data):
            meta_line = meta_line.strip().split(",")
            label = int(meta_line[-1])
            if label == 0: # train
                train_idx.append(int(meta_line[2]))
            elif label == 1:
                test_idx.append(int(meta_line[2]))
            else:
                raise ValueError(
                    "warning: fail to recognize train/test label {0} at line {1}".format(meta_line[1], lidx))

        return train_idx, test_idx

    def load_lda(self, path_lda):
        topic_dist = []
        # get metadata
        alpha = 0.
        try:
            with open(path_lda + "/final.other", "r") as f:
                lines = f.readlines()
        except:
            print "[warning] illegal path ignored: {}".format(path_lda)
            return topic_dist
        for line in lines:
            if "alpha" in line:
                alpha = float(line.strip().split()[-1])
                print "alpha:", alpha,
                break

        # get topic distribution
        with open(path_lda + "/final.gamma", "r") as f:
            lines = f.readlines()
        for line in lines:
            probs = line.strip().split()
            probs = [float(prob) - alpha for prob in probs]
            probs_sum = sum(probs)
            probs = [prob / probs_sum for prob in probs]
            topic_dist.append(probs)
        return topic_dist

    def gen_vocab(self, f_vocab=None):
        """
        generate vocab from loaded dataset
        vocab are saved as dict(): word -> idx
        """
        print "generating vocabulary ..."
        def _get_vocab(dataset, wordlist):
            for line in dataset:
                for word in line:
                    wordlist[word] += 1
            return wordlist

        wordlist = defaultdict(int)
        wordlist = _get_vocab(self.train.x_doc, wordlist)
        wordlist = _get_vocab(self.test.x_doc, wordlist)

        wordlist = sorted(wordlist.items(), key=itemgetter(1), reverse=True)
        freq_cnt = 0.
        total_cnt = 0.
        if not self.vocab_size:
            self.vocab_size = len(wordlist)
        for i, word in enumerate(wordlist):
            if len(self.vocab) < self.vocab_size:
                self.vocab[word[0]] = i
                freq_cnt += word[1]
            total_cnt += word[1]
        print "raw vocab size: {}".format(len(wordlist))
        print "final vocab size: {}".format(len(self.vocab))
        print "freq coverage: {}".format(freq_cnt / total_cnt)

        # save vocab
        if f_vocab:
            pkl.dump(self.vocab, open(f_vocab, "wb"))

    def load_data(self, f_corpus, f_meta_data):
        """
        load data from corpus and corpus mapping file
        :param f_corpus: corpus {company, date, docs}, tap separated
        :param f_meta_data: meta data, comma separated
                            {company, date, line index in corpus (starting 0), label, train(0)/test(1)}
        """
        print "loading from {}".format(f_corpus)
        self.train.clear()
        self.test.clear()

        with open(f_meta_data, "r") as f:
            meta_data = f.readlines()
        with open(f_corpus, "r") as f:
            corpus = f.readlines()

        for lidx, meta_line in enumerate(meta_data):
            meta_line = meta_line.strip().split(",")
            if len(meta_line) == 5:
                doc = word_tokenize(corpus[int(meta_line[2])].strip().split("\t")[-1]) # get doc from corpus
                label = int(meta_line[-2])
                if label == 0:
                    label = -1
                if int(meta_line[-1]) == 0:
                    self.train.x_doc.append(doc) # text
                    self.train.y.append(label) # label
                elif int(meta_line[-1]) == 1:
                    self.test.x_doc.append(doc)
                    self.test.y.append(label)
                else:
                    raise ValueError(
                        "warning: fail to recognize train/test label {0} at line {1}".format(meta_line[1], lidx))

            if len(meta_line) == 26:
                doc = word_tokenize(corpus[int(meta_line[2])].strip().split("\t")[-1])  # get doc from corpus
                label = int(meta_line[-2])
                if label == 0:
                    label = -1
                stock = [float(s) for s in meta_line[3:-2]]
                #fixme: NAN problem in stock change
                if np.any(np.isnan(np.array(stock))):
                    nan_idx = np.argwhere(np.isnan(np.array(stock)))
                    for idx in nan_idx:
                        stock[idx[0]] = 0.
                assert len(stock) == 21, "invalid number of stock changes"
                if int(meta_line[-1]) == 0:
                    self.train.x_doc.append(doc)  # text
                    self.train.x_stock.append(stock) # stock change, today and prev 20 days
                    self.train.y.append(label)  # label
                elif int(meta_line[-1]) == 1:
                    self.test.x_doc.append(doc)
                    self.test.x_stock.append(stock)
                    self.test.y.append(label)
                else:
                    raise ValueError(
                        "warning: fail to recognize train/test label {0} at line {1}".format(meta_line[1], lidx))

        if self.use_shuffle:
            self.shuffle()

    def shuffle(self):
        print "using shuffling...",
        self.sidx_train = np.random.permutation(len(self.train.y))
        self.train.x_doc = [self.train.x_doc[idx] for idx in self.sidx_train]
        if len(self.train.x_stock) > 0:
            self.train.x_stock = [self.train.x_stock[idx] for idx in self.sidx_train]
        self.train.y = [self.train.y[idx] for idx in self.sidx_train]

        self.sidx_test = np.random.permutation(len(self.test.y))
        self.test.x_doc = [self.test.x_doc[idx] for idx in self.sidx_test]
        if len(self.test.x_stock) > 0:
            self.test.x_stock = [self.test.x_stock[idx] for idx in self.sidx_test]
        self.test.y = [self.test.y[idx] for idx in self.sidx_test]
        print "done!"

    def set_valid(self, valid_portion=0.15):
        """
        set valid_portion of training data into validation set
        """
        n_sample = len(self.train.y)
        sidx = np.random.permutation(n_sample)
        n_train = int(np.round(n_sample * (1 - valid_portion)))
        self.valid.x_doc = [self.train.x_doc[idx] for idx in sidx[n_train:]]
        self.train.x_doc = [self.train.x_doc[idx] for idx in sidx[:n_train]]
        if len(self.train.x_stock) > 0:
            self.valid.x_stock = [self.train.x_stock[idx] for idx in sidx[n_train:]]
            self.train.x_stock = [self.train.x_stock[idx] for idx in sidx[:n_train]]
        self.valid.y = [self.train.y[idx] for idx in sidx[n_train:]]
        self.train.y = [self.train.y[idx] for idx in sidx[:n_train]]

    def save_data(self, f_dataset_out):
        print "saving to file ...",
        if len(self.train.x_stock) > 0:
            train = [[" ".join(line) for line in self.train.x_doc], self.train.x_stock, self.train.y]
            test = [[" ".join(line) for line in self.test.x_doc], self.test.x_stock, self.test.y]
            valid = [[" ".join(line) for line in self.valid.x_doc], self.valid.x_stock, self.valid.y]
        else:
            train = [[" ".join(line) for line in self.train.x_doc], self.train.y]
            test = [[" ".join(line) for line in self.test.x_doc], self.test.y]
            valid = [[" ".join(line) for line in self.valid.x_doc], self.valid.y]
        with open(f_dataset_out, "wb") as f:
            pkl.dump(train, f)
            pkl.dump(test, f)
            pkl.dump(valid, f)
        print "done!"
        print "train:", len(self.train.y), "valid:", len(self.valid.y), "test:", len(self.test.y)


if __name__ == "__main__":
    dir_data = "/home/yiren/Documents/time-series-predict/data/bp/"
    #dir_data = "/Users/ds/git/financial-topic-modeling/data/bpcorpus/"
    f_corpus = dir_data + "standard-query-corpus_pp.tsv"
    f_meta_data = dir_data + "corpus_labels_split_balanced_change.csv"
    f_dataset_out = dir_data + "dataset/corpus_bp_stock_cls.npz"
    f_vocab = dir_data + "dataset/vocab_stock.npz"

    dir_lda = dir_data + "lda_results/"
    f_lda_out = dir_data + "dataset/lda_features.npz"

    preprocessor = DataProcessor(overwrite=True, shuffle=True)
    preprocessor.run_docs(f_corpus=f_corpus, f_meta_data=f_meta_data, f_dataset_out=f_dataset_out, f_vocab=f_vocab)
    preprocessor.run_lda(dir_lda=dir_lda, f_meta_data=f_meta_data, f_lda_out=f_lda_out)
