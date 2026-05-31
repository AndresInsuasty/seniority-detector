# ejemplo junior — para el video
import requests

def get(x, y):
    data = requests.get(x)
    d2 = data.json()
    temp = []
    for i in range(len(d2)):
        a = d2[i]
        if a['active'] == True:
            temp.append(a)
    res = []
    for i in range(len(temp)):
        t = temp[i]
        n = t['name']
        e = t['email']
        s = t['score']
        if s > y:
            res.append({'name': n, 'email': e, 'score': s})
    return res

def save(data, path):
    f = open(path, 'w')
    import json
    f.write(json.dumps(data))
    f.close()
    print("guardado")

def main():
    data = get("http://localhost:8080/api/users", 50)
    print(data)
    save(data, "C:/Users/andre/output.json")
    print("listo")

main()
