import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score


# Load dataset
df = pd.read_csv("amazon.csv")

print(df.head())
print("Shape:", df.shape)


# Input and target
X = df["reviewText"]
y = df["Positive"]


# Split into training and testing data
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42
)


# Convert text into numbers using TF-IDF
vectorizer = TfidfVectorizer()

X_train = vectorizer.fit_transform(X_train)
X_test = vectorizer.transform(X_test)


# Create classifier
model = LogisticRegression(max_iter=1000)

# Train classifier
model.fit(X_train, y_train)


# Make predictions
y_pred = model.predict(X_test)


# Calculate accuracy
accuracy = accuracy_score(y_test, y_pred)

print("\nPredicted:", y_pred[:20])
print("Actual:   ", y_test.values[:20])

print("\nAccuracy:", accuracy)
print("Accuracy percentage:", accuracy * 100, "%")