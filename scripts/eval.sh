now=`date +%Y-%m-%d,%H:%m:%s`
nohup srun -p bj11part --gres=gpu:1 -n1 --job-name=MapNet_fire python eval.py --dataset 7Scenes --scene fire --model mapnet \
--weights logs/7Scenes_fire_posenet_posenet_learn_beta_learn_gamma/epoch_300.pth.tar \
--config_file configs/mapnet.ini --val 2>&1|tee logs/eval-${now}.log &