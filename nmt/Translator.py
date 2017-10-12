import nmt.utils.vocab_utils as vocab_utils
import torch
from torch.autograd import Variable
class Translator(object):
    def __init__(self, model, tgt_vocab_table, beam_size, USE_CUDA, max_length):
        self.model = model
        self.tgt_vocab_table = tgt_vocab_table
        self.beam_size = beam_size
        self.USE_CUDA = USE_CUDA
        self.max_length = max_length
        
        pass

    def decode(self, src_input, src_input_length):
        self.model.eval()
        encoder_outputs, encoder_hidden = self.model.encoder(src_input, src_input_length, None)
        decoder_init_hidden = encoder_hidden

        # Create starting vectors for decoder
        decoder_input = Variable(torch.LongTensor([vocab_utils.SOS_ID]), volatile=True) # SOS
        if self.USE_CUDA:
            decoder_input = decoder_input.cuda()
        
        if self.beam_size == 1:
            decoded_words = self._greedy_decode(decoder_init_hidden,decoder_input, encoder_outputs)
        else:
            pass


    def _greedy_decode(self, decoder_init_hidden, decoder_input, encoder_outputs):
        # Store output words and attention states
        decoded_words = []            
        # Run through decoder
        decoder_hidden = decoder_init_hidden
        for di in range(self.max_length):
            decoder_input = torch.unsqueeze(decoder_input,0)
            decoder_output, decoder_hidden = self.model.decoder(
                decoder_input, decoder_hidden, encoder_outputs
            )

            # Choose top word from output
            topv, topi = decoder_output.data.topk(1)
            ni = topi[0][0]
            ni = ni.cpu().numpy().tolist()[0]
            if  ni == vocab_utils.EOS_ID:
                decoded_words.append('<EOS>')
                break
            else:
                decoded_words.append(self.tgt_vocab_table.index2word[ni])
                
            # Next input is chosen word
            decoder_input = Variable(torch.LongTensor([ni]))
            if self.USE_CUDA: decoder_input = decoder_input.cuda()

        return decoded_words
        
        

    def _beam_decode(self):
        pass

