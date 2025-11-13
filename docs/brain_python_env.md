### Brain Python Env(old method)
#### Using Brain with docker python env
```
docker build -t intercode-python -f docker/python.Dockerfile .
```
```
brain = Brain() #default will use docker python env
```

#### Using Brain with rpyc env(If you don't want to use docker)
```
python docker/utils/python_server.py --port 3007
```
```
brain = Brain(python_env=RpycPythonEnv(port=3007))
```
#### Using Brain with Local Python env(be aware of this method, since llm can generate bad code)
```
brain = Brain(python_env=LocalPythonEnv(verbose=False))
```
#### Troubleshooting with docker python env
#### stop existing container if necessary
```
docker stop intercode-python_ic_ctr
docker rm intercode-python_ic_ctr
docker run -d -p 3006:3006 --name intercode-python_ic_ctr intercode-python
```
make sure container name intercode-python_ic_ctr is listening on 3006