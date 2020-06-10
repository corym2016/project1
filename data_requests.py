import requests

def main():
    res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "nRlh8TKQugPw3oRDVQ7QA", "isbns": "9781632168146"})
    if res.status_code != 200:
        raise Exception("ERROR CODE 404: this ISBN number was not in our database")
    data = res.json()
    print(data)

if __name__ == "__main__":
    main()
