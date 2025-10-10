---
layout: post
title: CellularEye-v1.0.0
subtitle: There's lots to learn!
gh-repo: daattali/beautiful-jekyll
gh-badge: [star, fork, follow]
tags: [test]
comments: true
mathjax: true
author: Purple Mountain Laboratories
---

{: .box-success}
This is a demo post to show you how to write blog posts with markdown.  I strongly encourage you to [take 5 minutes to learn how to write in markdown](https://markdowntutorial.com/) - it'll teach you how to transform regular text into bold/italics/tables/etc.<br/>I also encourage you to look at the [code that created this post](https://raw.githubusercontent.com/daattali/beautiful-jekyll/master/_posts/2020-02-28-sample-markdown.md) to learn some more advanced tips about using markdown in Beautiful Jekyll.

**Here is some bold text**

## Here is a secondary heading

[This is a link to a different site](https://deanattali.com/) and [this is a link to a section inside this page](#local-urls).

Here's a table:

| Number | Next number | Previous number |
| :------ |:--- | :--- |
| Five | Six | Four |
| Ten | Eleven | Nine |
| Seven | Eight | Six |
| Two | Three | One |

You can use [MathJax](https://www.mathjax.org/) to write LaTeX expressions. For example:
When \\(a \ne 0\\), there are two solutions to \\(ax^2 + bx + c = 0\\) and they are $$x = {-b \pm \sqrt{b^2-4ac} \over 2a}.$$

$a^2+b^2+c^2=112233$

How about a yummy crepe?

![Crepe](https://beautifuljekyll.com/assets/img/crepe.jpg)

It can also be centered!

![Crepe](https://beautifuljekyll.com/assets/img/crepe.jpg){: .mx-auto.d-block :}

Here's a code chunk:

~~~
var foo = function(x) {
  return(x + 5);
}
foo(3)
~~~

And here is the same code with syntax highlighting:

```javascript
var foo = function(x) {
  return(x + 5);
}
foo(3)
```

And here is the same code yet again but with line numbers:

{% highlight javascript linenos %}
var foo = function(x) {
  return(x + 5);
}
foo(3)
{% endhighlight %}

## Boxes
You can add notification, warning and error boxes like this:

### Notification

{: .box-note}
**Note:** This is a notification box.

### Warning

{: .box-warning}
**Warning:** This is a warning box.

### Error

{: .box-error}
**Error:** This is an error box.

## Local URLs in project sites {#local-urls}

When hosting a *project site* on GitHub Pages (for example, `https://USERNAME.github.io/MyProject`), URLs that begin with `/` and refer to local files may not work correctly due to how the root URL (`/`) is interpreted by GitHub Pages. You can read more about it [in the FAQ](https://beautifuljekyll.com/faq/#links-in-project-page). To demonstrate the issue, the following local image will be broken **if your site is a project site:**

![Crepe](/assets/img/crepe.jpg)

If the above image is broken, then you'll need to follow the instructions [in the FAQ](https://beautifuljekyll.com/faq/#links-in-project-page). Here is proof that it can be fixed:

![Crepe]({{ '/assets/img/crepe.jpg' | relative_url }})

<details markdown="1">
<summary>Click here!</summary>
Here you can see an **expandable** section
</details>

## Introduction

Welcome to the official homepage of the CellularEye dataset. CellularEye is a pioneering large-scale, multi-modal dataset designed for environmental perception research. It uniquely features IQ data collected from commercial communication equipment (BBU, AAU), alongside synchronized high-resolution optical, infrared, and weather data. Our goal is to bridge the gap between communication and sensing, empowering researchers to explore the future of integrated sensing and communication (ISAC).

![RV Map Example](assets/img/rv-map.gif)  ## Key Features

* **Commercial Cellular Signals**: Real-world IQ data from operational cellular network equipment, not simulated or lab-grade signals.
* **Rich Multi-modal Data**: Tightly synchronized data streams including IQ, visible spectrum video, infrared video, and detailed weather metrics.
* **Diverse Scenarios**: Covers a wide range of environmental conditions, including different times of day, weather patterns, and target activities.
* **Continuous Evolution**: CellularEye is a living dataset. We are committed to continuously updating it with more data and richer annotations.

## Getting Started & Downloads

We provide a Python-based development kit to help you easily read and visualize the data.

1.  **Read the Documentation**: Before downloading, please read our detailed [Data Description Document](link-to-your-doc.pdf). 2.  **Download the Data**: We recommend using the following links to download the dataset. For reproducibility, please specify the version you used in your research.

| Version | Release Date | Description | Download Link |
| :--- | :--- | :--- | :--- |
| **v1.0** | Oct 2025 | Initial public release. Contains 50 scenarios under various daytime conditions. | [Download from Zenodo](YOUR_ZENODO_LINK) |

## Citation

If you use the CellularEye dataset in your research, please cite our paper:

```bibtex
@inproceedings{yourteam2025cellulareye,
  title={{CellularEye}: A Large-Scale, Evolving Dataset for Environmental Perception...},
  author={Your Name and Your Team Members},
  booktitle={To Be Published},
  year={2025}
}
