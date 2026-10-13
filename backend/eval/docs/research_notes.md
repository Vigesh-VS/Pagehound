# Lightweight Crop Disease Detection on Edge Devices

## Abstract

We study whether small convolutional networks can detect leaf diseases accurately enough to run offline on low-cost phones used by farmers. Our best model, LeafNet-S, reaches 94.2 percent top-1 accuracy while using only 1.9 million parameters and running in 38 milliseconds per image on a budget Android phone.

## Motivation

Farmers in rural areas often lack stable internet, so cloud-based diagnosis tools fail exactly where they are most needed. A model that fits on a phone and works without connectivity could help farmers act before an infection spreads across a field. Large models such as ResNet-50 are accurate but too slow and too large for entry-level devices.

## Dataset

We collected 18,400 leaf images across four crops: tomato, potato, chilli and rice. Images were taken in real fields under natural light by volunteers using six different phone models. Agricultural experts labelled each image into one of 14 classes, including healthy leaves.

The data was split by farm rather than by image, so that no farm appears in both training and test sets. This prevents the model from memorising background details of a particular field. The final split is 70 percent training, 15 percent validation and 15 percent test.

## Method

LeafNet-S is based on depthwise separable convolutions with squeeze-and-excitation blocks. Input images are resized to 224 by 224 pixels. We trained for 120 epochs with the AdamW optimiser, a cosine learning-rate schedule starting at 0.003 and a batch size of 64.

Augmentation included random crops, colour jitter to simulate different lighting, and random blur to mimic camera shake. We also applied label smoothing of 0.1 to reduce overconfidence on ambiguous images.

After training, the model was quantised to 8-bit integers using post-training quantisation, which reduced the file size from 7.4 MB to 2.1 MB with an accuracy drop of only 0.3 points.

## Results

LeafNet-S achieved 94.2 percent accuracy on the held-out test farms, compared with 95.1 percent for ResNet-50 and 91.7 percent for MobileNetV2 at the same input size. ResNet-50 needs 412 milliseconds per image on the same phone, more than ten times slower than our model.

Per-class results show that early blight in potato was the hardest class, with an F1 score of 0.86, mainly because it is confused with late blight in its early stages. Healthy leaves were recognised with an F1 score of 0.99.

## Ablation Study

Removing squeeze-and-excitation blocks lowered accuracy by 1.8 points. Training without colour jitter lowered accuracy by 2.6 points, the largest drop of any single change, which shows how important lighting variation is in field images. Splitting by image instead of by farm inflated test accuracy to 98.0 percent, an overestimate caused by data leakage.

## Limitations

The dataset covers only four crops and one growing season, so performance on other crops or seasons is unknown. Images taken at night or with heavy shadow remain challenging. The model also cannot detect pest damage, which looks different from disease symptoms.

## Future Work

We plan to add six more crops, collect data across two additional seasons and test a version that suggests treatment steps in local languages. We will also explore knowledge distillation from ResNet-50 to close the remaining accuracy gap.
