import orjson

with open("projects/金茂/category_max_than_300.json", "r") as f:
    result = orjson.loads(f.read())

    o, j = 0, 0
    for i in result["products"]:
        o += 1
        skus = len(i["styleColors"])
        log.info(skus)
        j += skus
    log.info(o, j)
