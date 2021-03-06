import torch
import torch.nn as nn

class NMTModel(nn.Module):
    def __init__(self, enc_embedding, dec_embedding, encoder, decoder, generator):
        super(NMTModel, self).__init__()
        self.enc_embedding = enc_embedding
        self.dec_embedding = dec_embedding
        self.encoder = encoder
        self.decoder = decoder
        self.generator = generator

    def forward(self, src_inputs, tgt_inputs, src_lengths):

        # Run wrods through encoder

        enc_outputs, enc_hidden = self.encode(src_inputs, src_lengths, None)


        dec_init_hidden = self.init_decoder_state(enc_hidden, enc_outputs)
            
        dec_outputs , dec_hiddens, attn = self.decode(
                tgt_inputs, enc_outputs, dec_init_hidden
            )        

        return dec_outputs, attn



    def encode(self, input, lengths=None, hidden=None):
        emb = self.enc_embedding(input)
        enc_outputs, enc_hidden = self.encoder(emb, lengths, None)

        return enc_outputs, enc_hidden

    def init_decoder_state(self, enc_hidden, context):
        return enc_hidden

    def decode(self, input, context, state):
        emb = self.dec_embedding(input)
        dec_outputs , dec_hiddens, attn = self.decoder(
                emb, context, state
            )     

        return dec_outputs, dec_hiddens, attn
    
    def save_checkpoint(self, epoch, opt, filename):
        torch.save({'encoder_dict': self.encoder.state_dict(),
                    'decoder_dict': self.decoder.state_dict(),
                    'enc_embedding_dict': self.enc_embedding.state_dict(),
                    'dec_embedding_dict': self.dec_embedding.state_dict(),
                    'generator_dict': self.generator.state_dict(),
                    'opt': opt,
                    'epoch': epoch,
                    },
                   filename)

    def load_checkpoint(self, filename):   
        ckpt = torch.load(filename)
        self.enc_embedding.load_state_dict(ckpt['enc_embedding_dict'])
        self.dec_embedding.load_state_dict(ckpt['dec_embedding_dict'])
        self.encoder.load_state_dict(ckpt['encoder_dict'])
        self.decoder.load_state_dict(ckpt['decoder_dict'])
        self.generator.load_state_dict(ckpt['generator_dict'])
        epoch = ckpt['epoch']
        return epoch

