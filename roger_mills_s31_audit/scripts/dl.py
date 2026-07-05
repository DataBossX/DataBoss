import sys, base64
# reads base64 from stdin file, writes binary to output
inp, outp = sys.argv[1], sys.argv[2]
with open(inp) as f:
    data = f.read().strip()
with open(outp, 'wb') as f:
    f.write(base64.b64decode(data))
print("wrote", outp, "bytes:", len(base64.b64decode(data)))
