python -m ipybox build -t ghcr.io/gradion-ai/ipybox:minimal -d docker/dependencies-minimal.txt -r
python -m ipybox build -t ghcr.io/gradion-ai/ipybox:basic -d docker/dependencies-basic.txt -r
python -m ipybox build -t ghcr.io/gradion-ai/ipybox:example -d docker/dependencies-example.txt -r
python -m ipybox build -t ghcr.io/gradion-ai/ipybox:eval -d docker/dependencies-eval.txt -r
