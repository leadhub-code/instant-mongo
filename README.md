
instant-mongo
=============

Installation
------------

```sh
$ pip install git+https://github.com/messa/instant-mongo
```


Usage
-----

```python
from instant_mongo import InstantMongoDB
im = InstantMongoDB(data_dir=tmpdir / 'data')
with im:
    im.testdb.testcoll.insert({'foo': 'bar'})
    doc, = im.testdb.testcoll.find()
    assert doc['foo'] == 'bar'
```
