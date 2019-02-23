"""
Copyright (C) 2018 NVIDIA Corporation.  All rights reserved.
Licensed under the CC BY-NC-SA 4.0 license (https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode).
"""
 
import set_paths
from models.posenet import PoseNet, MapNet
from common.train import load_state_dict, step_feedfwd
from common.pose_utils import optimize_poses, quaternion_angular_error, qexp,\
  calc_vos_safe_fc, calc_vos_safe
from dataset_loaders.composite import MF
import argparse
import os
import os.path as osp
import sys
import numpy as np
import matplotlib
DISPLAY = 'DISPLAY' in os.environ
if not DISPLAY:
  matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import configparser
import torch.cuda
from torch.utils.data import DataLoader
from torchvision import transforms, models
import cPickle

# config
parser = argparse.ArgumentParser(description='Evaluation script for PoseNet and'
                                             'MapNet variants')
parser.add_argument('--dataset', type=str, choices=('7Scenes', 'RobotCar'),
                    help='Dataset')
parser.add_argument('--scene', type=str, help='Scene name')
parser.add_argument('--weights', type=str, help='trained weights to load')
parser.add_argument('--model', choices=('posenet', 'mapnet', 'mapnet++'),
  help='Model to use (mapnet includes both MapNet and MapNet++ since their'
       'evluation process is the same and they only differ in the input weights'
       'file')
parser.add_argument('--device', type=str, default='0', help='GPU device(s)')
parser.add_argument('--config_file', type=str, help='configuration file')
parser.add_argument('--val', action='store_true', help='Plot graph for val')
parser.add_argument('--output_dir', type=str, default=None,
  help='Output image directory')
parser.add_argument('--pose_graph', action='store_true',
  help='Turn on Pose Graph Optimization')
args = parser.parse_args()
if 'CUDA_VISIBLE_DEVICES' not in os.environ:
  os.environ['CUDA_VISIBLE_DEVICES'] = args.device

settings = configparser.ConfigParser()
with open(args.config_file, 'r') as f:
  settings.read_file(f)
seed = settings.getint('training', 'seed')
section = settings['hyperparameters']
dropout = section.getfloat('dropout')
if (args.model.find('mapnet') >= 0) or args.pose_graph:
  steps = section.getint('steps')
  skip = section.getint('skip')
  real = section.getboolean('real')
  variable_skip = section.getboolean('variable_skip')
  fc_vos = args.dataset == 'RobotCar'
  if args.pose_graph:
    vo_lib = section.get('vo_lib')
    sax = section.getfloat('s_abs_trans', 1)
    saq = section.getfloat('s_abs_rot', 1)
    srx = section.getfloat('s_rel_trans', 20)
    srq = section.getfloat('s_rel_rot', 20)

# model
feature_extractor = models.resnet18(pretrained=False)
posenet = PoseNet(feature_extractor, droprate=dropout, pretrained=False)
if (args.model.find('mapnet') >= 0) or args.pose_graph:
  model = MapNet(mapnet=posenet)
else:
  model = posenet
#model = torch.nn.DataParallel(model).cuda()
model.eval()
print(model)
# loss functions
t_criterion = lambda t_pred, t_gt: np.linalg.norm(t_pred - t_gt)
q_criterion = quaternion_angular_error

# load weights
weights_filename = osp.expanduser(args.weights)
if osp.isfile(weights_filename):
  loc_func = lambda storage, loc: storage#.cuda(0)
  checkpoint = torch.load(weights_filename, map_location=loc_func)
  load_state_dict(model, checkpoint['model_state_dict'])
  print 'Loaded weights from {:s}'.format(weights_filename)
else:
  print 'Could not load weights from {:s}'.format(weights_filename)
  sys.exit(-1)
    
model.feature_extractor= torch.nn.Sequential(*list(model.feature_extractor.children())[:-2])
model = model.feature_extractor
print(model)


data_dir = osp.join('..', 'data', args.dataset)
stats_filename = osp.join(data_dir, args.scene, 'stats.txt')
stats = np.loadtxt(stats_filename)
# transformer
data_transform = transforms.Compose([
  transforms.Resize(256),
  transforms.ToTensor(),
  transforms.Normalize(mean=stats[0], std=np.sqrt(stats[1]))])
target_transform = transforms.Lambda(lambda x: torch.from_numpy(x).float())

# read mean and stdev for un-normalizing predictions
pose_stats_file = osp.join(data_dir, args.scene, 'pose_stats.txt')
pose_m, pose_s = np.loadtxt(pose_stats_file)  # mean and stdev

# dataset
train = not args.val
if train:
  print 'Running {:s} on TRAIN data'.format(args.model)
else:
  print 'Running {:s} on VAL data'.format(args.model)
data_dir = osp.join('..', 'data', 'deepslam_data', args.dataset)
kwargs = dict(scene=args.scene, data_path=data_dir, train=train,
  transform=data_transform, target_transform=target_transform, seed=seed)
if (args.model.find('mapnet') >= 0) or args.pose_graph:
  if args.pose_graph:
    assert real
    kwargs = dict(kwargs, vo_lib=vo_lib)
  vo_func = calc_vos_safe_fc if fc_vos else calc_vos_safe
  data_set = MF(dataset=args.dataset, steps=steps, skip=skip, real=real,
                variable_skip=variable_skip, include_vos=args.pose_graph,
                vo_func=vo_func, no_duplicates=False, **kwargs)
  L = len(data_set.dset)
elif args.dataset == '7Scenes':
  from dataset_loaders.seven_scenes import SevenScenes
  data_set = SevenScenes(**kwargs)
  L = len(data_set)
elif args.dataset == 'RobotCar':
  from dataset_loaders.robotcar import RobotCar
  data_set = RobotCar(**kwargs)
  L = len(data_set)
else:
  raise NotImplementedError

# loader (batch_size MUST be 1)
batch_size = 1
assert batch_size == 1
loader = DataLoader(data_set, batch_size=batch_size, shuffle=False,
                    num_workers=5, pin_memory=True)

# activate GPUs
CUDA = torch.cuda.is_available()
torch.manual_seed(seed)
if CUDA:
  torch.cuda.manual_seed(seed)
  model.cuda()

pred_poses = np.zeros((L, 7))  # store all predicted poses
targ_poses = np.zeros((L, 7))  # store all target poses

# inference loop
for batch_idx, (data, target) in enumerate(loader):
  if batch_idx <100:
    continue
  if batch_idx % 200 == 0:
    print 'Image {:d} / {:d}'.format(batch_idx, len(loader))

  # indices into the global arrays storing poses
  if (args.model.find('vid') >= 0) or args.pose_graph:
    idx = data_set.get_indices(batch_idx)
  else:
    idx = [batch_idx]
  idx = idx[len(idx) / 2]

  # output : 1 x 6 or 1 x STEPS x 6
  _, output = step_feedfwd(data, model, CUDA, train=False)
  s = output.size()
  output = output.cpu().data.numpy()
  np.save('featuremap', output)
  np.save('pic', data.cpu().numpy())
  print('ok')
  break