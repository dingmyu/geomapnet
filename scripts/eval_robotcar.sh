now=`date +%Y-%m-%d,%H:%m:%s`
name=RobotCar_loop_mapnet_mapnet_learn_beta_learn_gamma
nohup srun -p bj11part --gres=gpu:1 -n1 --job-name=MapNet_loop python eval.py --dataset RobotCar --scene loop --model mapnet \
--weights logs/${name}/epoch_200.pth.tar \
--config_file configs/mapnet.ini --val 2>&1|tee logs/eval-${name}-${now}.log &
