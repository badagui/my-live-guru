import tiktoken

enc = tiktoken.get_encoding("cl100k_base")
my_string = "Hello World!"
token_count = len(enc.encode(my_string))
print('token_count', token_count)
