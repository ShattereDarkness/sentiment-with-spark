from pyspark.context import SparkContext
from pyspark.streaming import StreamingContext
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType
from pyspark.sql.functions import udf

from sklearn.model_selection import learning_curve
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.preprocessing import LabelEncoder
from sklearn.naive_bayes import MultinomialNB
from sklearn.linear_model import Perceptron, SGDClassifier
from sklearn.cluster import MiniBatchKMeans
from sklearn.metrics import accuracy_score, precision_score, recall_score, confusion_matrix, f1_score, classification_report
from sklearn.feature_extraction import text

from joblib import load

import matplotlib.pyplot as plt

import json
import re
import numpy as np
import argparse

parser = argparse.ArgumentParser(
    description='Streams a file to a Spark Streaming Context')
parser.add_argument('--batch-size', '-b', help='Batch size',
                    required=False, type=int, default=100)

# Initialize the spark context.
sc = SparkContext(appName="SpamStreaming")
ssc = StreamingContext(sc, 5)

spark = SparkSession(sc)

schema = StructType([StructField("feature0", StringType(), True), StructField("feature1", StringType(), True), StructField("feature2", StringType(), True)])

vectorizer = HashingVectorizer(alternate_sign=False)
le = LabelEncoder()
mnb = MultinomialNB()
sgd = SGDClassifier(warm_start=True)
per = Perceptron(warm_start=True)
kmeans = MiniBatchKMeans(n_clusters=2)

args = parser.parse_args()

count = 0
TEST_SIZE = int(3373/args.batch_size)

acc_clf1 = []
acc_clf2 = []
acc_clf3 = []
acc_clf4 = []

mnb = load('mnb.pkl')
per = load('per.pkl')
sgd = load('sgd.pkl')
kmeans = load('kmeans.pkl')

def removeNonAlphabets(s):
    s.lower()
    regex = re.compile('[^a-z\s]')
    s = regex.sub('', s)   
    return s

def removeStopWords(s):
    stop_words = list(text.ENGLISH_STOP_WORDS)
    res = []

    for sentence in s:
        words = sentence.split()
        temp = []
        for word in words:
            if word not in stop_words:
                temp.append(word)
        
        temp = ' '.join(temp)
        res.append(temp)
    
    return res

def print_stats(index, y, pred):
    accuracy = accuracy_score(y, pred)
    precision = precision_score(y, pred)
    recall = recall_score(y, pred)
    conf_m = confusion_matrix(y, pred)
    f1 = f1_score(y, pred)

    print(f"\naccuracy: %.3f" %accuracy)
    # print(f"precision: %.3f" %precision[-1])
    # print(f"recall: %.3f" %recall[-1])
    # print(f"f1-score : %.3f" %f1[-1])
    print(f"confusion matrix: ")
    print(conf_m)

    if index == 1:
        acc_clf1.append(accuracy)
    elif index==2:
        acc_clf2.append(accuracy)
    elif index==3:
        acc_clf3.append(accuracy)
    elif index==4:
        acc_clf4.append(accuracy)

    # print(classification_report(y, pred, labels = [0, 1]))

def plotting():
    x_axis = [i for i in range(1, TEST_SIZE + 1)]
    print(acc_clf1)
    plt.plot(x_axis, acc_clf1, color = "red")  
    plt.plot(x_axis, acc_clf2, color = "blue") 
    plt.plot(x_axis, acc_clf3, color = "green") 
    plt.plot(x_axis, acc_clf4, color = "black") 
    plt.ylabel("Accuracy")     
    plt.xlabel("Num Of Batches")     
    plt.show()

def func(rdd):
    global count, TEST_SIZE
    l = rdd.collect()

    if len(l):  
        count += 1

        df = spark.createDataFrame(json.loads(l[0]).values(), schema)

        df_list = df.collect()
        
        # Remove non alphabetic characters
        non_alphabetic = [(removeNonAlphabets(x['feature0'] + ' ' + x['feature1'])) for x in df_list]

        # Remove stop words
        no_stop_words = removeStopWords(non_alphabetic)

        X_test = vectorizer.fit_transform(no_stop_words)

        y_test = le.fit_transform(np.array([x['feature2']  for x in df_list]))

        #multinomial nb
        pred = mnb.predict(X_test)
        print("\nMultinomial NB: ")
        print_stats(1, y_test, pred)

        #perceptron
        pred = per.predict(X_test)
        print("\nPerceptron: ")
        print_stats(2, y_test, pred)

        #sgdclassifier
        pred = sgd.predict(X_test)
        print("\nSGD Classifier: ")
        print_stats(3, y_test, pred)

        #k means clustering
        pred = kmeans.predict(X_test)
        print("\nK-Means: ")
        print_stats(4, y_test, pred)
    
    if count == TEST_SIZE:
        plotting()
        count = 0


lines = ssc.socketTextStream("localhost", 6100)

lines.foreachRDD(func)

ssc.start()
ssc.awaitTermination()
ssc.stop()