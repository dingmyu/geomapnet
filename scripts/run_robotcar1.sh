now=`date +%Y-%m-%d,%H:%m:%s`
srun -p bj11part --gres=gpu:4 -n1 --job-name=MapNet_fire python -u train.py --dataset RobotCar --scene loop --config_file configs/mapnet.ini --model mapnet --device 0,1,2,3 --learn_beta --learn_gamma --suffix new 2>&1|tee logs/train-${now}.log &
