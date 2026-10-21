import json,re,sys,collections
raw=json.load(open(sys.argv[1]))['contentSnippet']
# the connector markdown-escapes the JSON: undo it
s=raw.replace('\\[','[').replace('\\]',']').replace('\\_','_').replace('\\*','*')
s=re.sub(r'[ \t]+\n','\n',s)
data=json.loads(s)
json.dump(data,open(sys.argv[2],'w'))
print('records:',len(data))
per=collections.Counter(r['source'] for r in data)
for k in sorted(per): print('  %-24s %4d pages'%(k,per[k]))
vocab=collections.Counter(h for r in data for h in r['hits'])
print('hit vocabulary (%d terms):'%len(vocab))
for t,c in vocab.most_common(): print('   %-22s %5d'%(t,c))
print('pages with >=1 hit:',sum(1 for r in data if r['hits']))
print('pages with 0 hits  :',sum(1 for r in data if not r['hits']))
