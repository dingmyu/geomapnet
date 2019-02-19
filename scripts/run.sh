now=`date +%Y-%m-%d,%H:%m:%s`
srun -p bj11part --gres=gpu:4 -n1 --job-name=MapNet_fire python train.py --suffix reduce3 --dataset 7Scenes --scene fire --config_file configs/posenet.ini --model posenet --device 0,1,2,3 --learn_beta --learn_gamma 2>&1|tee logs/train-${now}.log &
