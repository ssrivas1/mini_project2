# -*- coding: utf-8 -*-
"""Mini Project 2.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1jjxL7a-l47TIT4-Da9EL7FY-xWnPNlAb

# Mini Project - Team John Doe
"""

pip install pyspark

pip install findspark

import findspark
findspark.init()

from pyspark.sql import SparkSession
from pyspark.conf import SparkConf
from pyspark.sql.types import * 
import pyspark.sql.functions as F
from pyspark.sql.functions import col, asc,desc
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from pyspark.sql import SQLContext
from pyspark.mllib.stat import Statistics
import pandas as pd
from pyspark.sql.functions import udf
from pyspark.ml.feature import OneHotEncoder, StringIndexer, VectorAssembler,StandardScaler
from pyspark.ml import Pipeline
from sklearn.metrics import confusion_matrix

spark=SparkSession.builder \
.master ("local[*]")\
.appName("part3")\
.getOrCreate()

from google.colab import drive
drive.mount('/content/drive')

sc=spark.sparkContext
sqlContext=SQLContext(sc)

import os
os.getcwd()

# Read data
df=spark.read \
 .option("header","True")\
 .option("inferSchema","True")\
 .option("sep",",")\
 .csv("/content/drive/MyDrive/Mini Project 2/XYZ_Bank_Deposit_Data_Classification.csv", sep=';')
print("There are",df.count(),"rows",len(df.columns),
      "columns" ,"in the data.")

# Show sample data
df.show(5)

# Data Types of columns
df.printSchema()

# Renaming columns so that they can be used easily

df = df.withColumnRenamed("emp.var.rate", "emp_var_rate")\
        .withColumnRenamed("cons.price.idx", "cons_price_idx")\
        .withColumnRenamed("cons.conf.idx", "cons_conf_idx")\
        .withColumnRenamed("nr.employed","nr_employed")

"""## Exploratory Data Analysis"""

# Checking for Null Values
from pyspark.sql.functions import isnan, when, count, col
df.select([count(when(isnan(c), c)).alias(c) for c in df.columns]).toPandas().transpose()

# Check basic statistics
df.describe().toPandas().transpose()

# Target variable Distribution
df.groupBy("y").count().show()

# Finding categorical variables

cat_features = [t[0] for t in df.dtypes if t[1] == 'string']

# checking value count of each category
for i in cat_features:
    df.groupBy(i).count().show()

# We could see 'unknown' as category in multiple variables. Checking count of missing values

cat_missing_values = pd.DataFrame(columns = ['column_name','Number_of_missing_values'])
for c in cat_features:
    x = df.select(c).where(df[c] =='unknown').count()
    cat_missing_values = cat_missing_values.append({'column_name' : c, 'Number_of_missing_values' : x},
            ignore_index = True)
    
cat_missing_values

# Imputing Unknown values in marital status with mode

marital_mode = df.groupby("marital").count().orderBy("count", ascending=False).first()[0]
df=df.withColumn("marital",when(df.marital=='unknown',marital_mode).otherwise(df.marital))

# Showing value counts
df.groupBy('marital').count().show()

# Combining 'illiterate' and 'unknown' category together in education column

df = df.withColumn("education",when(df.education=='illiterate','unknown').otherwise(df.education))

# Similarly, for default column, combining 'yes' and 'unknown' together

df = df.withColumn("default",when(df.default=='yes','unknown').otherwise(df.default))

# Checking the dataset
df.groupBy('default').count().show()

# Adding age label

from pyspark.ml.feature import Bucketizer
bucketizer = Bucketizer(splits=[15, 26, 36, 46, 56, 66, 76, 100],inputCol="age", outputCol="age_buckets")
df = bucketizer.setHandleInvalid("keep").transform(df)

df.select('age', 'age_buckets').show()

t = {0.0:"15-25", 1.0: "26-35", 2.0:"36-45", 3.0: "46-55", 4.0: "56-65", 5.0: "66-75", 6.0: "Above 75"}
udf_foo = udf(lambda x: t[x], StringType())
df = df.withColumn("age_label", udf_foo("age_buckets"))

df.select('age', 'age_buckets', 'age_label').show()

df_P = df.toPandas()

df_P['age_label'].value_counts().reindex(["15-25",  "26-35", "36-45",  "46-55", "56-65",  "66-75", "Above 75"]).plot(kind='bar')

df = df.drop(*['age','age_label'])

# Binning number of days last contacted

# First checking the distribution of Pdays
pdays_values = df.select('pdays').distinct().rdd.map(lambda r: r[0]).collect()
pdays_values.sort()
print(pdays_values)

# Adding pdays buckets

from pyspark.ml.feature import Bucketizer
bucketizer = Bucketizer(splits=[0, 6, 11, 16, 21, 30, 1000],inputCol="pdays", outputCol="pdays_buckets")
df = bucketizer.setHandleInvalid("keep").transform(df)

# Adding pdays label
t = {0.0:"Less than 5 days", 1.0: "6-10 days", 2.0:"11-15 days", 3.0: "16-20 days", 4.0: "More than 20 days", 5.0: "Never"}
udf_foo = udf(lambda x: t[x], StringType())
df = df.withColumn("pdays_label", udf_foo("pdays_buckets"))

df = df.drop(*['pdays','pdays_buckets'])

df_P = df.toPandas()
df_P['pdays_label'].value_counts().reindex(["Less than 5 days", "6-10 days", "11-15 days",  "16-20 days", "More than 20 days", "Never"]).plot(kind='barh')

df.groupBy('pdays_label').count().show()

# Getting numeric features
int_features = [t[0] for t in df.dtypes if t[1] == 'int']
double_features =  [t[0] for t in df.dtypes if t[1] == 'double']
numeric_features = int_features + double_features
numeric_features

numeric_features_df = df.select(numeric_features)

# Finding correlation between all numeric features

col_names =numeric_features_df.columns
features = numeric_features_df.rdd.map(lambda row: row[0:])
corr_mat=Statistics.corr(features, method="pearson")
corr_df = pd.DataFrame(corr_mat)
corr_df.index, corr_df.columns = col_names, col_names

corr_df

# Creating correlation heatmap
sns.set(rc={'axes.facecolor':'black', 'figure.facecolor':'white'})
sns.heatmap(corr_df, linewidth = 2)

# Dropping highly correlated variables
cols = ['emp_var_rate', 'euribor3m']
df = df.drop(*cols)

# Marital staus with target variable
plt.figure(figsize=(8,6))
sns.countplot(x= 'marital',data=df_P, palette='rainbow',hue='y')

# Housing staus with target variable
plt.figure(figsize=(8,6))
sns.countplot(x= 'housing',data=df_P, palette='Paired',hue='y')

# Bank default status with target variable
plt.figure(figsize=(8,6))
sns.countplot(x= 'default',data=df_P, palette='rainbow',hue='y')

# Loan status

plt.figure(figsize=(8,6))
sns.countplot(x= 'loan',data=df_P,hue='y')

# Marital staus with target variable
plt.figure(figsize=(8,6))
sns.countplot(x= 'contact',data=df_P, palette='tab10',hue='y')

# Marital staus with target variable
plt.figure(figsize=(8,6))
sns.countplot(x= 'poutcome',data=df_P, palette='husl',hue='y')

# Marital staus with target variable
plt.figure(figsize=(8,6))
sns.countplot(x= 'housing',data=df_P, palette='rainbow',hue='y')

# pdays with target variable
plt.figure(figsize=(8,6))
sns.countplot(x= 'pdays_label',data=df_P, palette='rainbow',hue='y')

df.crosstab('job','y').toPandas().set_index('job_y').transpose()

df.crosstab('education','y').toPandas().set_index('education_y').transpose()

df.crosstab('month','y').toPandas().set_index('month_y').transpose()

df.crosstab('day_of_week','y').toPandas().set_index('day_of_week_y').transpose()

# Univariate analysis of numeric variable
df_P = df.toPandas()
sns.FacetGrid(df_P , hue ='y', size=5).map(sns.distplot, "previous").add_legend()

sns.boxplot(x = 'y', y = 'duration', data=df_P)
plt.show()

df1 = df.toPandas()
df1.to_csv('cleaned_df.csv')

"""## Modelling

### Data Preparation
"""

## Reading processed dataset

df=spark.read \
 .option("header","True")\
 .option("inferSchema","True")\
 .option("sep",",")\
 .csv("/content/drive/MyDrive/Mini Project 2/final_data.csv")
print("There are",df.count(),"rows",len(df.columns),
      "columns" ,"in the data.")

# Numeric variables
numeric_features = [feature[0] for feature in df.dtypes if (feature[1] == 'int' or feature[1] == 'double')]
print(numeric_features)
# Cateogrical variables
categorical_features = [t[0] for t in df.dtypes if t[1] == 'string']
categorical_features.remove('y')
print(categorical_features)

from pyspark.ml.feature import OneHotEncoder, StringIndexer, VectorAssembler
from pyspark.ml.feature import StandardScaler

categoricalColumns = categorical_features
stages = []
for categoricalCol in categoricalColumns:
    stringIndexer = StringIndexer(inputCol = categoricalCol, outputCol = categoricalCol + 'Index')
    encoder = OneHotEncoder(inputCols=[stringIndexer.getOutputCol()], outputCols=[categoricalCol + "classVec"])
    stages += [stringIndexer, encoder]
    
label_stringIdx = StringIndexer(inputCol = 'y', outputCol = 'label')
stages += [label_stringIdx]

numericCols = numeric_features
assemblerInputs = [c + "classVec" for c in categoricalColumns] + numericCols
assembler = VectorAssembler(inputCols=assemblerInputs, outputCol="features")
stages += [assembler]



scaler = StandardScaler(inputCol = "features",
                        outputCol = "scaledFeatures",
                        withStd = True,
                        withMean = True)
stages += [scaler]

cols = df.columns
cols.remove('y')
cols

from pyspark.ml import Pipeline
pipeline = Pipeline(stages = stages)
pipelineModel = pipeline.fit(df)
df = pipelineModel.transform(df)
selectedCols = ['label', 'scaledFeatures']
df = df.select(selectedCols)
df.printSchema()

pd.DataFrame(df.take(5), columns=df.columns).transpose()

train, test = df.randomSplit([0.7, 0.3], seed = 2018)
print("Training Dataset Count: " + str(train.count()))
print("Test Dataset Count: " + str(test.count()))

"""## Logistic Regression"""

from pyspark.ml.classification import LogisticRegression
from pyspark.ml.tuning import ParamGridBuilder, CrossValidator
from pyspark.ml.evaluation import BinaryClassificationEvaluator
from pyspark.mllib.evaluation import BinaryClassificationMetrics

evaluator = BinaryClassificationEvaluator()

from pyspark.ml.classification import LogisticRegression
lr = LogisticRegression(featuresCol = 'scaledFeatures', labelCol = 'label', maxIter=10)

lrparamGrid = (ParamGridBuilder()
             .addGrid(lr.regParam, [0.01, 0.1])
             .addGrid(lr.elasticNetParam, [0.0, 0.25])
             .addGrid(lr.maxIter, [1, 5, 10])
             .build())

lrevaluator = BinaryClassificationEvaluator(rawPredictionCol="rawPrediction", metricName = "areaUnderROC")

# Create 5-fold CrossValidator
lrcv = CrossValidator(estimator = lr,
                    estimatorParamMaps = lrparamGrid,
                    evaluator = lrevaluator,
                    numFolds = 5)

lrcvModel = lrcv.fit(train)
print(lrcvModel)

lrpredictions = lrcvModel.transform(test)

print('Accuracy:', lrevaluator.evaluate(lrpredictions))
print('AUC:', BinaryClassificationMetrics(lrpredictions['label','prediction'].rdd).areaUnderROC)
print('PR:', BinaryClassificationMetrics(lrpredictions['label','prediction'].rdd).areaUnderPR)
# lrModel = lr.fit(train)

# lrpredictions = lrModel.transform(test)
# trainingSummary = lrModel.summary

# print("Test Area Under ROC: " + str(evaluator.evaluate(lrpredictions, {evaluator.metricName: "areaUnderROC"})))

"""## Decision tree"""

from pyspark.ml.classification import DecisionTreeClassifier
from pyspark.ml.tuning import ParamGridBuilder, CrossValidator
from pyspark.ml.evaluation import BinaryClassificationEvaluator


dt = DecisionTreeClassifier(featuresCol = 'scaledFeatures', labelCol = 'label', maxDepth = 3)

dtparamGrid = (ParamGridBuilder()
             .addGrid(dt.maxDepth, [2, 5, 10])
             .addGrid(dt.maxBins, [10, 20])
             .build())

dtevaluator = BinaryClassificationEvaluator(rawPredictionCol="rawPrediction")

# Create 5-fold CrossValidator
dtcv = CrossValidator(estimator = dt,
                      estimatorParamMaps = dtparamGrid,
                      evaluator = dtevaluator,
                      numFolds = 5)

dtcvModel = dtcv.fit(train)
print(dtcvModel)

dtpredictions = dtcvModel.transform(test)
#predictions.select('label', 'rawPrediction', 'prediction', 'probability').show(10)


print('Accuracy:', dtevaluator.evaluate(dtpredictions))
print('AUC:', BinaryClassificationMetrics(dtpredictions['label','prediction'].rdd).areaUnderROC)
print('PR:', BinaryClassificationMetrics(dtpredictions['label','prediction'].rdd).areaUnderPR)

"""## Random Forest Classifier"""

from pyspark.ml.classification import RandomForestClassifier
from pyspark.ml.tuning import ParamGridBuilder, CrossValidator
from pyspark.ml.evaluation import BinaryClassificationEvaluator


rf = RandomForestClassifier(labelCol="label", featuresCol="scaledFeatures")

rfparamGrid = (ParamGridBuilder()

               .addGrid(rf.maxDepth, [2, 5, 10])

               .addGrid(rf.maxBins, [5, 10, 20])

               .addGrid(rf.numTrees, [5, 20, 50])
             .build())

rfevaluator = BinaryClassificationEvaluator(rawPredictionCol="rawPrediction")

# Create 5-fold CrossValidator
rfcv = CrossValidator(estimator = rf,
                      estimatorParamMaps = rfparamGrid,
                      evaluator = rfevaluator,
                      numFolds = 5)

rfcvModel = rfcv.fit(train)
print(rfcvModel)

rfpredictions = rfcvModel.transform(test)

print('Accuracy:', rfevaluator.evaluate(rfpredictions))
print('AUC:', BinaryClassificationMetrics(rfpredictions['label','prediction'].rdd).areaUnderROC)
print('PR:', BinaryClassificationMetrics(rfpredictions['label','prediction'].rdd).areaUnderPR)

"""## Gradient-Boosted Tree Classifier"""

from pyspark.ml.classification import GBTClassifier
from pyspark.ml.tuning import ParamGridBuilder, CrossValidator
from pyspark.ml.evaluation import BinaryClassificationEvaluator

gb = GBTClassifier(labelCol="label", featuresCol="scaledFeatures")

gbparamGrid = (ParamGridBuilder()
             .addGrid(gb.maxDepth, [2, 5])
             .addGrid(gb.maxBins, [10, 20])
             .addGrid(gb.maxIter, [5, 10])
             .build())

gbevaluator = BinaryClassificationEvaluator(rawPredictionCol="rawPrediction")

# Create 5-fold CrossValidator
gbcv = CrossValidator(estimator = gb,
                      estimatorParamMaps = gbparamGrid,
                      evaluator = gbevaluator,
                      numFolds = 5)

gbcvModel = gbcv.fit(train)
print(gbcvModel)

gbpredictions = gbcvModel.transform(test)

print('Accuracy:', gbevaluator.evaluate(gbpredictions))
print('AUC:', BinaryClassificationMetrics(gbpredictions['label','prediction'].rdd).areaUnderROC)
print('PR:', BinaryClassificationMetrics(gbpredictions['label','prediction'].rdd).areaUnderPR)

"""## Linear Support Vector Classification"""

from pyspark.ml.tuning import ParamGridBuilder, CrossValidator
from pyspark.ml.evaluation import BinaryClassificationEvaluator
from pyspark.mllib.evaluation import BinaryClassificationMetrics
from pyspark.ml.classification import LinearSVC

lsvc = LinearSVC(featuresCol='scaledFeatures', \
                 labelCol='label')

lsvcparamGrid = (ParamGridBuilder()
             .addGrid(lsvc.maxIter, [10, 20])
             .addGrid(lsvc.regParam, [0.01, 0.1])
             .build())

lsvcevaluator = BinaryClassificationEvaluator(rawPredictionCol="rawPrediction")

# Create 5-fold CrossValidator
lsvccv = CrossValidator(estimator = lsvc,
                      estimatorParamMaps = lsvcparamGrid,
                      evaluator = lsvcevaluator,
                      numFolds = 5)

lsvcModel = lsvccv.fit(train)
print(lsvcModel)

lsvcpredictions = lsvcModel.transform(test)

print('Accuracy:', gbevaluator.evaluate(lsvcpredictions))
print('AUC:', BinaryClassificationMetrics(lsvcpredictions['label','prediction'].rdd).areaUnderROC)
print('PR:', BinaryClassificationMetrics(lsvcpredictions['label','prediction'].rdd).areaUnderPR)

"""## Confusion Matrix for Best model"""

class_names=[1.0,0.0]
import itertools
def plot_confusion_matrix(cm, classes,
                          normalize=False,
                          title='Confusion matrix',
                          cmap=plt.cm.Blues):
    """
    This function prints and plots the confusion matrix.
    Normalization can be applied by setting `normalize=True`.
    """
    if normalize:
        cm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]
        print("Normalized confusion matrix")
    else:
        print('Confusion matrix, without normalization')

    print(cm)

    plt.imshow(cm, interpolation='nearest', cmap=cmap)
    plt.title(title)
    plt.colorbar()
    tick_marks = np.arange(len(classes))
    plt.xticks(tick_marks, classes, rotation=45)
    plt.yticks(tick_marks, classes)

    fmt = '.2f' if normalize else 'd'
    thresh = cm.max() / 2.
    for i, j in itertools.product(range(cm.shape[0]), range(cm.shape[1])):
        plt.text(j, i, format(cm[i, j], fmt),
                 horizontalalignment="center",
                 color="white" if cm[i, j] > thresh else "black")

    plt.tight_layout()
    plt.ylabel('True label')
    plt.xlabel('Predicted label')

y_true = rfpredictions.select("label")
y_true = y_true.toPandas()

y_pred = rfpredictions.select("prediction")
y_pred = y_pred.toPandas()

cnf_matrix = confusion_matrix(y_true, y_pred,labels=class_names)
#cnf_matrix
plt.figure()
plot_confusion_matrix(cnf_matrix, classes=class_names,
                      title='Confusion matrix')
plt.show()

"""## ROC-AUC Plot"""

trainingSummary = rfModel.summary
roc = trainingSummary.roc.toPandas()
plt.plot(roc['FPR'],roc['TPR'])
plt.ylabel('False Positive Rate')
plt.xlabel('True Positive Rate')
plt.title('ROC Curve')
plt.show()
print('Training set areaUnderROC: ' + str(trainingSummary.areaUnderROC))



"""# K-means clustering"""

from pyspark.ml.clustering import KMeans
from pyspark.ml.evaluation import ClusteringEvaluator

silhouette_score=[]
evaluator = ClusteringEvaluator(predictionCol='prediction', featuresCol='scaledFeatures', \
                                metricName='silhouette', distanceMeasure='squaredEuclidean')
for i in range(2,10):
    
    KMeans_algo=KMeans(featuresCol='scaledFeatures', k=i)
    
    KMeans_fit=KMeans_algo.fit(df)
    
    output=KMeans_fit.transform(df)
    
    
    
    score=evaluator.evaluate(output)
    
    silhouette_score.append(score)
    
    print("Silhouette Score:",score)

#Visualizing the silhouette scores in a plot
import matplotlib.pyplot as plt
fig, ax = plt.subplots(1,1, figsize =(8,6))
ax.plot(range(2,10),silhouette_score)
ax.set_xlabel('k')
ax.set_ylabel('cost')

from pyspark.ml.clustering import KMeans
from pyspark.ml.evaluation import ClusteringEvaluator

KMeans_=KMeans(featuresCol='scaledFeatures', k=4) 
KMeans_Model=KMeans_.fit(df)
KMeans_Assignments=KMeans_Model.transform(df)

KMeans_Assignments.groupBy('prediction').count().show()

from pyspark.ml.feature import PCA as PCAml
pca = PCAml(k=2, inputCol="scaledFeatures", outputCol="pca")
pca_model = pca.fit(df)
pca_transformed = pca_model.transform(df)

import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np

x_pca = np.array(pca_transformed.rdd.map(lambda row: row.pca).collect())

cluster_assignment = np.array(KMeans_Assignments.rdd.map(lambda row: row.prediction).collect()).reshape(-1,1)

pca_data = np.hstack((x_pca,cluster_assignment))

pca_df = pd.DataFrame(data=pca_data, columns=("1st_principal", "2nd_principal","cluster_assignment"))
sns.FacetGrid(pca_df,hue="cluster_assignment", height=6).map(plt.scatter, '1st_principal', '2nd_principal' ).add_legend()

plt.show()

"""## Save and load model"""

bestModel = rfcvModel.bestModel
bestModel


rf1 = RandomForestClassifier(labelCol="label", featuresCol="scaledFeatures",numTrees=50)
rfModel1 = rf1.fit(train)
rfModel1.save("/finalModel")
pipelineModel = rfModel1.load("/finalModel")
train = pipelineModel.transform(train)

rfModel1.save("/content/drive/MyDrive/Mini Project 2/ChampionModel")

"""## Feature Importance"""

rf = RandomForestClassifier(labelCol="label", featuresCol="scaledFeatures")
rfModel = rf.fit(train)

## Gini-Based Method for Gradient Boosted Tree
def ExtractFeatureImportance(featureImp, dataset, featuresCol):
    list_extract = []
    for i in dataset.schema[featuresCol].metadata["ml_attr"]["attrs"]:
        list_extract = list_extract + dataset.schema[featuresCol].metadata["ml_attr"]["attrs"][i]
    varlist = pd.DataFrame(list_extract)
    varlist['score'] = varlist['idx'].apply(lambda x: featureImp[x])
    return(varlist.sort_values('score', ascending = False))
  
  
#ExtractFeatureImportance(model.stages[-1].featureImportances, dataset, "features")
dataset_fi = ExtractFeatureImportance(rfModel.featureImportances, df, "scaledFeatures")
dataset_fi = sqlContext.createDataFrame(dataset_fi)
display(dataset_fi)

dataset_fi_pd = dataset_fi.toPandas()
dataset_fi_pd.head(10)