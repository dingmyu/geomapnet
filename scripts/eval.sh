now=`date +%Y-%m-%d,%H:%m:%s`
name=7Scenes_chess_mapnet_mapnet_learn_beta_learn_gamma
nohup srun -p bj11part --gres=gpu:1 -n1 --job-name=MapNet_fire python eval.py --dataset 7Scenes --scene chess --model mapnet \
--weights logs/${name}/epoch_300.pth.tar \
--config_file configs/mapnet.ini --val 2>&1|tee logs/eval-${name}-${now}.log &
