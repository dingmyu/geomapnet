now=`date +%Y-%m-%d,%H:%m:%s`
suffix=res18
scene=fire
srun -p bj11part --gres=gpu:4 -n1 --job-name=MapNet_fire python train.py --suffix ${suffix} --dataset 7Scenes --scene ${scene} --config_file configs/posenet.ini --model posenet --device 0,1,2,3 --learn_beta --learn_gamma 2>&1|tee logs/train-${scene}-${suffix}-${now}.log &
