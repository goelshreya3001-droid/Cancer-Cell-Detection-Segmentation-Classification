# 🔬 Automated Two-Stage Deep Learning Pipeline for Cancer Nuclei Detection, Phenotyping & Explainability

An end-to-end computational pathology research framework for nuclear instance segmentation, multi-class cell phenotyping, and explainable AI on Hematoxylin & Eosin (H&E) histopathology images.

This pipeline utilizes a decoupled, two-stage deep learning architecture: pixel-level localization via a **PyTorch U-Net** followed by instance-level classification using a **5-class CNN** with **Class-Balanced Focal Loss**. It incorporates **Macenko stain normalization**, **Grad-CAM visual attribution**, and empirical **zero-shot cross-dataset generalization** across multi-organ cohorts.

---

## 📌 Methodology & Technical Workflow
[Raw H&E Whole-Slide Tile]
│
▼
[01: Patch Extraction] ──────► Slices 1000x1000 slides to 256x256 patches
│
▼
[02: U-Net Segmentation] ────► Pixel-level foreground/background nuclear mask
│
▼
[03: Watershed Separation] ──► Distance transform splits touching/overlapping nuclei
│
▼
[04: Multi-Class CNN] ────────► 32x32 single-cell crops classified into 5 phenotypes
│
┌──────┴──────────────────────────┐
▼                                 ▼
[gradcam.ipynb]             [evaluate_generalization.ipynb]
(Feature attribution maps)  (Zero-shot benchmark on MoNuSeg multi-organ slides)

---

## 🌟 Key Research Highlights

1. **Domain Invariance via Stain Normalization:** Employs Macenko optical density decomposition to isolate Hematoxylin and Eosin absorbance vectors, correcting color variations introduced by different scanners and staining protocols.
2. **Two-Stage Cascaded Architecture:**
   * **Stage 1 (Segmentation):** U-Net with skip-connections trained with compound Dice and Binary Cross-Entropy loss.
   * **Instance Topological Splitting:** Euclidean Distance Transform coupled with marker-controlled Watershed segmentation to separate fused or overlapping nuclear clusters.
   * **Stage 2 (Phenotyping):** Deep CNN dedicated to single-cell classification into five distinct biological categories.
3. **Class-Balanced Focal Loss:** Implemented custom focal loss ($\gamma=2.0$) with dynamic inverse-frequency class weighting to mitigate severe data imbalance between dominant epithelial cells and sparse stromal/immune populations.
4. **Zero-Shot Cross-Dataset Generalization:** Evaluated directly on the multi-organ **MoNuSeg** benchmark without fine-tuning, demonstrating out-of-domain transfer robustness.
5. **Model Explainability (Grad-CAM):** Registers hooks on the final convolutional layer of the classifier to audit internal representations, verifying that decisions are driven by cellular atypia and hyperchromasia rather than slide artifacts.

---

## 📂 Repository Structure

```text
├── models/
│   ├── unet.pth                         # Trained U-Net segmentation weights
│   └── classifier.pth                   # Trained 5-class nuclei classifier weights
├── .gitignore                           # Excludes checkpoints, raw data, and cache
├── 01_explore_and_extract_patches.ipynb  # Dataset parsing & uniform patch generation
├── 02_train_unet.ipynb                  # U-Net architecture & segmentation training
├── 03_evaluate_unet.ipynb               # Metric evaluation (Dice/IoU) & Watershed splitting
├── 04_nuclei_classification.ipynb       # 5-class phenotyping & Focal Loss training
├── evaluate_generalization.ipynb        # Out-of-domain evaluation on MoNuSeg benchmark
└── gradcam.ipynb                        # Explainable AI (Grad-CAM) visual attention maps

🧬 Nuclear Phenotyping Scheme
The classifier labels isolated single-cell instances (32×32 crops) across five distinct categories:

Class ID	Biological Phenotype	Pathological Significance
0	Miscellaneous / Other	Non-cellular tissue components, necrotic debris, unclassified cells
1	Inflammatory	Lymphocytes and plasma cells (used to compute TIL immune response)
2	Healthy Epithelial	Non-malignant tissue lining and organized glandular structures
3	Malignant Epithelial	Cancerous cells characterized by nuclear enlargement and pleomorphism
4	Spindle / Stromal	Connective tissue cells, endothelial cells, and fibroblasts
📓 Notebook Walkthrough
01_explore_and_extract_patches.ipynb
Loads raw CoNSeP whole-slide histology tiles (1000×1000 pixels) and associated ground truth .mat files.

Parses nuclear bounding coordinates and binary segmentation masks.

Slices tiles into uniform 256×256 patches with overlap filtering to eliminate empty background regions.

02_train_unet.ipynb
Builds a 4-level PyTorch U-Net architecture with batch normalization and ReLU activations.

Implements a compound loss function combining Binary Cross-Entropy (BCE) and Dice Loss.

Trains the spatial localization model and saves best checkpoint weights to models/unet.pth.

03_evaluate_unet.ipynb
Evaluates segmentation accuracy using Dice Similarity Coefficient (DSC) and Intersection over Union (IoU).

Implements the Distance Transform + Watershed post-processing pipeline to split adjacent, touching cell instances into distinct centroids.

04_nuclei_classification.ipynb
Extracts 32×32 crops centered on identified nuclear centroids.

Trains a multi-class CNN using Focal Loss with inverse-frequency class balancing to handle extreme class distribution skew.

Evaluates multi-class precision, recall, and F1-scores, saving model weights to models/classifier.pth.

evaluate_generalization.ipynb
Tests the CoNSeP-trained models zero-shot on unseen slides from the multi-organ MoNuSeg dataset (covering breast, kidney, liver, prostate, and bladder tissues).

Performs an ablation study comparing Raw Biopsies vs. Macenko Stain-Normalized Biopsies to quantitatively measure domain transfer retention.

gradcam.ipynb
Implements Gradient-weighted Class Activation Mapping using PyTorch forward and backward hooks.

Generates heatmaps overlaid on single-cell patches to highlight regions of interest (e.g., chromatin texture, nuclear boundary irregularity) influencing the classification decision.

🧪 Benchmark Datasets
CoNSeP (Colorectal Nuclear Segmentation & Phenotypes): 41 H&E colorectal adenocarcinoma histology tiles from the University of Warwick with ~24,000 individually annotated nuclei.

MoNuSeg (Multi-Organ Nuclei Segmentation): Multi-center clinical dataset featuring tissue types across diverse human organs used to benchmark out-of-domain cross-dataset generalization.

🛠️ Requirements & Setup
Environment Setup
Bash
# Clone the repository
git clone [https://github.com/your-username/cancer-nuclei-detection-pipeline.git](https://github.com/your-username/cancer-nuclei-detection-pipeline.git)
cd cancer-nuclei-detection-pipeline

# Create and activate conda environment
conda create -n cancer_cell python=3.10 -y
conda activate cancer_cell

# Install required packages
pip install torch torchvision numpy scipy scikit-image opencv-python matplotlib jupyterlab
Running the Notebooks
Launch JupyterLab to inspect or run any stage of the pipeline:

Bash
jupyter lab
📄 License
This repository is released under the MIT License.
