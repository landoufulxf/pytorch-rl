import torch
from torch.autograd import Variable
import numpy as np
import torch.nn as nn
import torch.nn.functional as F

# Variational Autoencoder with the option for tuning the disentaglement- Refer to the paper - beta VAE
class VAE(nn.Module):
    def __init__(self, conv_layers, z_dimension, pool_kernel_size,
                 conv_kernel_size, input_channels, height, width, hidden_dim):
        super(VAE, self).__init__()

        self.conv_layers = conv_layers
        self.conv_kernel_shape = conv_kernel_size
        self.pool = pool_kernel_size
        self.z_dimension = z_dimension
        self.in_channels = input_channels
        self.height = height
        self.width = width
        self.hidden = hidden_dim

        # Encoder Architecture
        self.conv1 = nn.Conv2d(in_channels=self.in_channels, out_channels=self.conv_layers,
                               kernel_size=self.conv_kernel_shape, padding=1, stride=2)
        self.conv2 = nn.Conv2d(in_channels=self.conv_layers, out_channels=self.conv_layers*2,
                               kernel_size=self.conv_kernel_shape, padding=1, stride=2)
        # Size of input features = HxWx2C
        self.linear1 = nn.Linear(in_features=self.height//4*self.width//4*self.conv_layers*2, out_features=self.hidden)
        self.bn3 = nn.BatchNorm1d(self.hidden)
        self.latent_mu = nn.Linear(in_features=self.hidden, out_features=self.z_dimension)
        self.latent_logvar = nn.Linear(in_features=self.hidden, out_features=self.z_dimension)
        self.relu = nn.ReLU(inplace=True)


        # Decoder Architecture
        self.linear1_decoder = nn.Linear(in_features=self.z_dimension,
                                         out_features=self.height//4 * self.width//4 * self.conv_layers*2)
        self.bn4 = nn.BatchNorm1d(self.conv_layers*2)
        self.conv3 = nn.ConvTranspose2d(in_channels=self.conv_layers*2, out_channels=self.conv_layers,
                                        kernel_size=self.conv_kernel_shape-1, stride=2)
        self.bn5 = nn.BatchNorm2d(self.conv_layers)
        self.output = nn.ConvTranspose2d(in_channels=self.conv_layers, out_channels=self.in_channels,
                                        kernel_size=self.conv_kernel_shape-1, stride=2)


    def encode(self, x):
        # Encoding the input image to the mean and var of the latent distribution
        bs, _, _, _ = x.shape
        conv1 = self.conv1(x)
        conv1 = self.relu(conv1)
        conv2 = self.conv2(conv1)
        conv2 = self.relu(conv2)

        pool = conv2.view((bs, -1))

        linear = self.linear1(pool)
        linear = self.relu(linear)
        mu = self.latent_mu(linear)
        logvar = self.latent_logvar(linear)

        return mu, logvar

    def reparameterize(self, mu, logvar):
        # Reparameterization trick as shown in the auto encoding variational bayes paper
        if self.training:
            std = logvar.mul(0.5).exp_()
            eps = Variable(std.data.new(std.size()).normal_())
            return eps.mul(std).add_(mu)
        else:
            return mu

    def decode(self, z):
        # Decoding the image from the latent vector
        z = self.linear1_decoder(z)
        z = z.view((-1, self.conv_layers*2, self.height//4, self.width//4))
        z = self.conv3(z)
        z = self.relu(z)
        output = self.output(z)
        return output

    def forward(self, x):
        mu, logvar = self.encode(x)
        z = self.reparameterize(mu, logvar)
        output = self.decode(z)
        return output, mu, logvar, z


# Denoising Autoencoder
class DAE(nn.Module):
    def __init__(self, conv_layers,
                 conv_kernel_size, pool_kernel_size,
                 height, width, input_channels, hidden_dim,
                 noise_scale=0.1):
        super(DAE, self).__init__()

        self.conv_layers = conv_layers
        self.conv_kernel_shape = conv_kernel_size
        self.pool = pool_kernel_size
        self.height = height
        self.width = width
        self.input_channels = input_channels
        self.hidden = hidden_dim
        self.noise_scale = noise_scale


        # Encoder
        # ﻿four convolutional layers, each with kernel size 4 and stride 2 in both the height and width dimensions.
        self.conv1 = nn.Conv2d(in_channels=self.input_channels, out_channels=self.conv_layers,
                               kernel_size=self.conv_kernel_shape, stride=2, padding=1)
        self.conv2 = nn.Conv2d(in_channels=self.conv_layers, out_channels=self.conv_layers,
                               kernel_size=self.conv_kernel_shape,  stride=2, padding=1)
        self.conv3 = nn.Conv2d(in_channels=self.conv_layers, out_channels=self.conv_layers*2,
                               kernel_size=self.conv_kernel_shape, stride=2, padding=1)

        self.conv4 = nn.Conv2d(in_channels=self.conv_layers*2, out_channels=self.conv_layers*2,
                               kernel_size=self.conv_kernel_shape, stride=2, padding=1)

        self.relu = nn.ReLU(inplace=True)

        # Bottleneck Layer
        self.bottleneck = nn.Linear(in_features=self.height//16*self.width//16*self.conv_layers*2,
                                    out_features=self.hidden)


        # Decoder
        self.linear_decoder = nn.Linear(in_features=hidden_dim, out_features=self.height//16*self.width//16*self.conv_layers*2)
        self.conv5 = nn.ConvTranspose2d(in_channels=self.conv_layers*2,
                                        out_channels=self.conv_layers*2, stride=2, kernel_size=self.conv_kernel_shape-1
                                        )

        self.conv6 = nn.ConvTranspose2d(in_channels=self.conv_layers*2,
                                        out_channels=self.conv_layers * 2, stride=2, kernel_size=self.conv_kernel_shape-1
                                        )

        self.conv7 = nn.ConvTranspose2d(in_channels=self.conv_layers * 2,
                                        out_channels=self.conv_layers, stride=2, kernel_size=self.conv_kernel_shape-1
                                        )

        self.conv8 = nn.ConvTranspose2d(in_channels=self.conv_layers,
                                        out_channels=self.conv_layers, stride=2, kernel_size=self.conv_kernel_shape-1
                                        )
        # Decoder output
        self.output = nn.Conv2d(in_channels=self.conv_layers, out_channels=self.input_channels,
                                kernel_size=self.conv_kernel_shape-2)

    def encode(self, x):
        x = self.conv1(x)
        x = self.relu(x)

        x = self.conv2(x)
        x = self.relu(x)

        x = self.conv3(x)
        x = self.relu(x)

        x = self.conv4(x)
        x = self.relu(x)

        x = x.view((-1, self.height//16*self.width//16*self.conv_layers*2))

        out = self.bottleneck(x)
        return out
    
    def decode(self, encoded):
        x = self.linear_decoder(encoded)
        x  = x.view((-1, self.conv_layers*2, self.height//16, self.width//16))
        x = self.conv5(x)
        x = self.relu(x)

        x = self.conv6(x)
        x = self.relu(x)

        x = self.conv7(x)
        x = self.relu(x)

        x = self.conv8(x)
        x = self.relu(x)

        out = self.output(x)
        return out

    def forward(self, image):
        # Adding noise
        n, _, _, _ = image.shape
        noise = Variable(torch.randn(n, 3, self.height, self.width))
        #image = torch.mul(image + 0.25, 0.1 * noise)
        image = torch.add(image, self.noise_scale*noise)
        encoded = self.encode(image)
        decoded = self.decode(encoded)
        return decoded, encoded




