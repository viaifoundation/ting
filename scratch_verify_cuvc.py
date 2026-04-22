from text_cleaner import clean_text_for_tts

test_texts = [
    "耶穌曰、○我實語汝、○人若不生於水及聖靈、○則不能入上帝國。○",
    "『我實語汝、』",
    "其處有主使者．○",
    "字旁小點‧表示譯者所加。",
    "有些舊版使用◯大圓號分隔段落。",
    "這裡有一個 [WH] 標籤需要移除。"
]

print("--- CUVC Punctuation Handling Test ---")
for original in test_texts:
    cleaned = clean_text_for_tts(original)
    print(f"Original: {original}")
    print(f"Cleaned:  {cleaned}")
    print("-" * 20)
