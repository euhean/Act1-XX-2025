# **Project Name: Act1-XX-2025**

## **Project Overview**

This repository is for collaborative development in **Act1-XX-2025**. Each team member has their own branch for working on their part of the project. Follow the instructions below to ensure smooth collaboration.

## **Getting Started**

### **1. Clone the Repository**

If you haven't already cloned the repository, do so with:

```sh
git clone https://github.com/euhean/Act1-XX-2025.git
cd Act1-XX-2025
```

### **2. Check Remote Repository and Status**

To verify the configured remote repositories:

```sh
git remote -v
```

To check the current branch status:

```sh
git status
```

### **3. Fetch the Latest Updates**

Before starting any work, always update your local repository:

```sh
git fetch origin
```

### **4. Switch to Your Assigned Branch**

Each classmate should work on their **own branch**. Replace `your-branch-name` with your assigned name:

```sh
git checkout your-branch-name
```

If the branch doesn’t exist locally yet, create it:

```sh
git checkout -b your-branch-name origin/your-branch-name
```

### **5. Make Changes and Save Your Work**

After making your changes, add and commit them:

```sh
git add .
git commit -m "Describe your changes here"
```

### **6. Push Your Changes to GitHub**

Push your updates to your branch:

```sh
git push origin your-branch-name
```

### **7. Delete Your Branch (If No Longer Needed)**

Once you have completed your work and no longer need your branch:

```sh
git branch -d your-branch-name
```

To remove it from GitHub as well:

```sh
git push origin --delete your-branch-name
```

## **Poetry & Virtual Environment Setup (Fedora)**

To work with dependencies and the virtual environment, follow these steps:

### **1. Install Poetry**

If Poetry is not installed, run:

```sh
curl -sSL https://install.python-poetry.org | python3 -
```

### **2. Add Poetry to Your PATH (Fedora)**

Ensure Poetry is added to your PATH by adding the following to your shell configuration file (`~/.bashrc` or `~/.bash_profile`):

```sh
export PATH="$HOME/.local/bin:$PATH"
```

Then, apply the changes:

```sh
source ~/.bashrc  # or source ~/.bash_profile
```

### **3. Set Up the Virtual Environment and Install Dependencies**

Navigate to the project directory and install dependencies:

```sh
poetry install
```

If dependencies are missing or out of sync, run:

```sh
poetry update
```

### **4. Activate the Virtual Environment**

Activate the environment manually:

```sh
source $(poetry env info --path)/bin/activate
```

### **5. Add New Dependencies**

If you need to install a new package:

```sh
poetry add package-name
```

### **6. Exit the Virtual Environment**

To deactivate the environment:

```sh
deactivate
```

## **Need Help?**

If you face any issues, ask in the team chat or check GitHub documentation: [GitHub Docs](https://docs.github.com/)

---

Happy coding! 🚀

