Too make sure this PaleoBook will be truly yours (and not this template), check `_config.yml`, `_toc.hml`, and `meta_data/chapter_meta.hml` and make sure that you have changed all fields that should be specific to your PaleoBook (which is most)

1. have an environment in which `jupyter-book` is installed (you can follow the env setup readme in the template repo)
2. `jupyter-book build .` will build the html in the current directory (it needs to be top level so that it sees all the stuff)
3. open `index.html` in a browser and inspect your work. In addtion to checking your prose and figures, make sure that navigation bar titles are informative and that nothing points to the PaleoBook template instead of your work 
4. move `_build` to a directory called `docs`
5. `pip install ghp-import`
6. follow the instructions for getting a classic token for `you>settings>developer tools` (very bottom menu option). The following categories will suffice: `admin:gpg_key`, `admin:org`, `admin:org_hook`, `admin:public_key`, `admin:repo_hook`, `audit_log`, `repo`, `workflow`
7. `export GH_TOKEN=ghp_yourTokenHere` (update _ghp_yourTokenHere_ with your token string)
8. `git remote set-url origin https://$GH_TOKEN@github.com/<username>/<repo>.git` (change _username_ and _repo_)
8. `ghp-import -n -p -f docs/_build/html`
8. add `docs/_build/` to your `.gitignore` (if you used this template it will already be there)
9. push the contents to github 
10. from your github repo, navigate to `Actions> ` to check that the book deployed properly and click the url for your published book to bask in your glory!

To contribute your book to the PaleoBooks Gallery:
1. Make sure your repo is public. (This is both part of the mission of PaleoBooks and also a practical necessity on our end for accessing relevant metadata.)
2. One more time, check `meta_data/chapter_meta.yml`, `_config.yml`, `_toc.yml`! **In particular,** add appropriate thumbnails to `thumbnails` (specify in `chapter_meta.yml`) and update the `tags` associated with each chapter (also in `chapter_meta.yml`)!
3. Submit a **Gallery Submission** issue via the PaleoBooks repo ([accessible here](https://github.com/LinkedEarth/PaleoBooks/issues)) using the provided template. As an example, these are the relevant inputs for submitting this book to the Gallery (for reasons I can't explain the github url stem is being replaced by the github logo in the bullets below, but please type the full url):

- repo_name: paleobook_template
- repo_url: [`https://github.com/jordanplanders/paleobook_template`](https://github.com/jordanplanders/paleobook_template)
- host: [`https://jordanplanders.github.io`](https://jordanplanders.github.io)
- user: jordanplanders
- landingpage: readme
- landingpage_url: [`https://jordanplanders.github.io/paleobook_template/readme.html`](https://jordanplanders.github.io/paleobook_template/readme.html)
- config_url: [`https://github.com/jordanplanders/paleobook_template/blob/main/_config.yml`](https://github.com/jordanplanders/paleobook_template/blob/main/_config.yml)
- cookbook_loc: [`https://jordanplanders.github.io/paleobook_template`](https://jordanplanders.github.io/paleobook_template)
- branch: main