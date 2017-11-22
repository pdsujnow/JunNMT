import nmt.model_helper as model_helper
import nmt.utils.misc_utils as utils
import nmt.utils.vocab_utils as vocab_utils
import nmt.utils.data_utils as data_utils
import argparse
from nmt.Trainer import Trainer
from nmt.Loss import NMTLossCompute
from nmt.Optim import Optim
from nmt.Trainer import Statistics
from tensorboardX import SummaryWriter
import codecs
import os
import shutil
import re
import torch
import torch.nn as nn
from torch import cuda
import nmt.IO
parser = argparse.ArgumentParser()
parser.add_argument("-config", type=str)
parser.add_argument("-nmt_dir", type=str)
parser.add_argument("-data", type=str)
parser.add_argument('-gpuid', default=[], nargs='+', type=int)

args = parser.parse_args()
opt = utils.load_hparams(args.config)

summery_writer = SummaryWriter(opt.log_dir)


if args.gpuid:
    cuda.set_device(args.gpuid[0])
       
def report_func(global_step, epoch, batch, num_batches,
                start_time, lr, report_stats):
    """
    This is the user-defined batch-level traing progress
    report function.
    Args:
        epoch(int): current epoch count.
        batch(int): current batch count.
        num_batches(int): total number of batches.
        start_time(float): last report time.
        lr(float): current learning rate.
        report_stats(Statistics): old Statistics instance.
    Returns:
        report_stats(Statistics): updated Statistics instance.
    """
    if batch % opt.steps_per_stats == -1 % opt.steps_per_stats:
        report_stats.print_out(epoch, batch+1, num_batches, start_time,summery_writer)
        report_stats.log("progress", summery_writer, global_step, learning_rate=lr, 
                                                                  ppl=report_stats.ppl(),
                                                                  accuracy=report_stats.accuracy())
        report_stats = Statistics()

    return report_stats




def make_train_data_iter(train_data, opt):
    """
    This returns user-defined train data iterator for the trainer
    to iterate over during each train epoch. We implement simple
    ordered iterator strategy here, but more sophisticated strategy
    like curriculum learning is ok too.
    """
    return nmt.IO.OrderedIterator(
                dataset=train_data, batch_size=opt.batch_size,
                device=args.gpuid[0] if args.gpuid else -1,                
                repeat=False, sort=False)


def make_valid_data_iter(valid_data, opt):
    """
    This returns user-defined validate data iterator for the trainer
    to iterate over during each validate epoch. We implement simple
    ordered iterator strategy here, but more sophisticated strategy
    is ok too.
    """
    return nmt.IO.OrderedIterator(
                dataset=valid_data, batch_size=opt.batch_size,
                device=args.gpuid[0] if args.gpuid else -1,                                
                train=False, sort=False)

def load_fields(train, valid):
    fields = nmt.IO.load_fields(
                torch.load(args.data + '.vocab.pt'))
    fields = dict([(k, f) for (k, f) in fields.items()
                  if k in train.examples[0].__dict__])
    train.fields = fields
    valid.fields = fields

    print(' * vocabulary size. source = %d; target = %d' %
          (len(fields['src'].vocab), len(fields['tgt'].vocab)))

    return fields


def build_model(model_opt, fields):
    print('Building model...')
    model = model_helper.create_base_model(model_opt, len(fields['src'].vocab), len(fields['tgt'].vocab), fields['tgt'].vocab.stoi[nmt.IO.PAD_WORD])

    print(model)

    return model


def build_optim(model, optim_opt):
    optim = Optim(optim_opt.optim_method, 
                  optim_opt.learning_rate,
                  optim_opt.max_grad_norm,
                  optim_opt.learning_rate_decay,
                  optim_opt.weight_decay,
                  optim_opt.start_decay_at)
                  
    optim.set_parameters(model.parameters())

    return optim

def check_save_model_path(opt):
    if not os.path.exists(opt.out_dir):
        os.makedirs(opt.out_dir)
        print('saving config file to %s ...'%(opt.out_dir))
        # save config.yml
        shutil.copy(args.config, os.path.join(opt.out_dir,'config.yml'))


def test_bleu():
    # os.system('export CUDA_VISIBLE_DEVICES=0')
    os.system('python3 %s/translate.py \
                --config %s \
                --src_in %s \
                --tgt_out %s \
                --model %s \
                --data %s' %(args.nmt_dir,
                             os.path.join(opt.out_dir,'config.yml'),
                             opt.dev_src_file,
                             os.path.join(opt.out_dir,'translate.tmp'),
                             utils.latest_checkpoint(opt.out_dir),
                             args.data,
                            )
            )
    output = os.popen('perl %s/tools/multi-bleu.pl %s < %s'%(args.nmt_dir,
                                                             ' '.join(opt.dev_tgt_file),
                                                             os.path.join(opt.out_dir,'translate.tmp')
                                                             ))
    output = output.read()
    # Get bleu value
    bleu_val = re.findall('BLEU = (.*?),',output,re.S)[0]
    bleu_val = float(bleu_val)
    return bleu_val



def train_model(model, train_data, valid_data, fields, optim):

    train_iter = make_train_data_iter(train_data, opt)
    valid_iter = make_valid_data_iter(valid_data, opt)

    train_loss = NMTLossCompute(len(fields['tgt'].vocab), fields['tgt'].vocab.stoi[nmt.IO.PAD_WORD])
    valid_loss = NMTLossCompute(len(fields['tgt'].vocab), fields['tgt'].vocab.stoi[nmt.IO.PAD_WORD]) 

    if opt.USE_CUDA:
        train_loss = train_loss.cuda()
        valid_loss = valid_loss.cuda()    

    trainer = Trainer(opt,
                      model,
                      train_iter,
                      valid_iter,
                      train_loss,
                      valid_loss,
                      optim)

    num_train_epochs = opt.num_train_epochs
    for step_epoch in  range(num_train_epochs):
        # 1. Train for one epoch on the training set.
        train_stats = trainer.train(step_epoch, report_func)
        print('Train perplexity: %g' % train_stats.ppl())

        

        # 2. Validate on the validation set.
        valid_stats = trainer.validate()
        print('Validation perplexity: %g' % valid_stats.ppl())
        trainer.epoch_step(valid_stats.ppl(),step_epoch)
        
        valid_bleu = test_bleu()
        train_stats.log("train", summery_writer, step_epoch, 
                        ppl=train_stats.ppl(),
                        learning_rate=optim.lr, 
                        accuracy=train_stats.accuracy())
        valid_stats.log("valid", summery_writer, step_epoch, 
                        ppl=valid_stats.ppl(),
                        learning_rate=optim.lr, 
                        bleu=valid_bleu,
                        accuracy=valid_stats.accuracy())

        
def main():

    # Load train and validate data.
    print("Loading train and validate data from '%s'" % args.data)
    train = torch.load(args.data + '.train.pt')
    valid = torch.load(args.data + '.valid.pt')
    
    # Load fields generated from preprocess phase.
    fields = load_fields(train, valid)

    # Build model.
    model = build_model(opt, fields)
    check_save_model_path(opt)

    # Build optimizer.
    optim = build_optim(model, opt)


    if opt.USE_CUDA:
        model = model.cuda()

    # Do training.
    train_model(model, train, valid, fields, optim)

if __name__ == '__main__':
    main()