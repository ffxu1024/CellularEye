"""Numerical panel layouts used by the CellularEye detection examples."""
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/cellulareye-experiment-plots')
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.ticker import MaxNLocator


def render(domains,subsets,background,out):
    u=72/72.27
    plt.rcParams.update({'font.family':'DejaVu Sans','font.weight':'normal','font.size':6.75*u,
        'axes.labelsize':7.25*u,'axes.titlesize':7.25*u,'xtick.labelsize':6.75*u,
        'ytick.labelsize':6.75*u,'axes.linewidth':.5,'pdf.fonttype':42,'svg.fonttype':'none'})
    metrics=['map','fp','miss','mae']
    methods=['Real','Pure Statistics']

    def save(fig,folder,name):
        folder.mkdir(parents=True,exist_ok=True)
        for ext in ['pdf','svg','png']:
            fig.savefig(folder/f'{name}.{ext}',dpi=450,facecolor='white')
        plt.close(fig)

    def style(ax):
        ax.spines[['top','right']].set_visible(False)
        ax.grid(axis='y',color='#D8DDE2',linewidth=.4);ax.set_axisbelow(True)

    # Reference comparison: fixed 66-frame set, two fixed model families.
    for key,ylabel,limit,ticks in [('map','mAP50–95',1,[0,.5,1]),('fp','FP/frame',1.2,[0,.6,1.2]),
            ('miss','Miss rate',.5,[0,.25,.5]),('mae','Center error (bins)',65,[0,30,60])]:
        rows=[next(r for r in domains if r['domain']=='Reference' and r['method']==m and r['metric']==key) for m in methods]
        fig=plt.figure(figsize=(120/72.27,85/72.27));ax=fig.add_axes([30/120,10/85,83/120,69/85])
        mean=np.array([r['mean'] for r in rows]);sd=np.array([r['sample_sd'] for r in rows]);x=np.arange(2)
        ax.bar(x,mean,color=['#BCD6ED','#C5DFB4'],width=.55,edgecolor='black',linewidth=.55,zorder=3)
        ax.errorbar(x,mean,yerr=sd,fmt='none',ecolor='black',elinewidth=.55,capsize=1.5,capthick=.55,zorder=4)
        ax.set(xlim=(-.65,1.65),ylim=(0,limit),ylabel=ylabel,xticks=[],yticks=ticks);ax.yaxis.labelpad=2
        ax.tick_params(length=2,width=.5,pad=2);style(ax)
        for i,(v,s) in enumerate(zip(mean,sd)):
            ax.annotate(f'{v:.2f}' if key=='mae' else f'{v:.3f}',(i,v+s),xytext=(0,3),textcoords='offset points',
                ha='center',va='bottom',fontsize=6.75*u,bbox=dict(facecolor='white',edgecolor='none',pad=.12))
        save(fig,out/'reference',key)
    fig=plt.figure(figsize=(480/72.27,12/72.27))
    fig.legend([Patch(facecolor=c,edgecolor='black',linewidth=.55) for c in ['#BCD6ED','#C5DFB4']],
        ['Real baseline','Sim+AWGN'],loc='center',ncol=2,frameon=False,handlelength=.9,columnspacing=.8)
    save(fig,out/'reference','shared_legend')
    specs=[
        ('overall',domains,'domain',['Reference','Trajectory','Weather','BS','Beam','Time'],['Ref.','Traj.','Rain','BS','Beam','Time']),
        ('trajectory',[r for r in subsets if r['category']=='trajectory'],'group',
            ['Reference','real_Traj-1-1-202609_None_Go_sunny_snr15.0_tx23_rx23_beam14_w30h30',
             'real_Traj-3_None_Back_sunny_snr15.0_tx23_rx23_beam14_w30h30','real_Traj-4_None_Go_sunny_snr15.0_tx23_rx23_beam14_w30h30'],
            ['Ref.','1-1\nGo','3\nBack','4\nGo']),
        ('weather',[r for r in subsets if r['category']=='weather'],'group',
            ['Reference','real_Traj-1-1_None_Back_rainy_snr15.0_tx23_rx23_beam14_w30h30','real_Traj-1_None_Back_rainy_snr15.0_tx23_rx23_beam14_w30h30'],
            ['Ref.','1-1\nBack','1\nBack']),
        ('bs',domains,'domain',['Reference','BS'],['Ref.','BS22']),
        ('beam',domains,'domain',['Reference','Beam'],['Ref.','Beam13']),
        ('time',domains,'domain',['Reference','Time'],['Ref.','2025-12']),
    ]
    handles=[]
    for category,rows,field,groups,labels in specs:
        # Match the row-specific archived limits, including the shared reference.
        chosen=[r for r in rows if r[field] in groups]
        for key,ylabel in zip(metrics,['mAP50–95','FP/frame','Miss rate','Center error (bins)']):
            bottom={'overall':24,'trajectory':20,'weather':20,'bs':10,'beam':10,'time':10}[category]
            w,h=120,58+bottom;fig=plt.figure(figsize=(w/72.27,h/72.27));ax=fig.add_axes([25/w,bottom/h,70/w,49/h])
            for i,method in enumerate(methods):
                selected=[next(r for r in chosen if r[field]==g and r['method']==method and r['metric']==key) for g in groups]
                yy=[r['mean'] for r in selected];sd=[r['sample_sd'] for r in selected]
                line=ax.errorbar(np.arange(len(groups))+(i-.5)*.05,yy,yerr=sd,
                    color=['#527FA3','#C47D55'][i],ecolor=['#527FA3','#C47D55'][i],marker=['o','^'][i],
                    markerfacecolor=['#BCD6ED','#F8CAAC'][i],markeredgecolor='black',markeredgewidth=.4,
                    markersize=2.7,linewidth=.8,elinewidth=.5,capsize=1.1,capthick=.5,zorder=3)
                if category=='overall' and key=='map':handles.append(line)
            top=max(r['mean']+r['sample_sd'] for r in chosen if r['metric']==key)*1.12
            ax.set_ylim(0,max(1,top) if key in ['map','miss'] else max(top,.01))
            if key in ['map','miss']:ax.set_yticks([0,.5,1])
            else:ax.yaxis.set_major_locator(MaxNLocator(nbins=3,min_n_ticks=3,prune='upper'))
            ax.set(xlim=(-.3,len(groups)-.7),xticks=np.arange(len(groups)),xticklabels=labels,ylabel=ylabel)
            ax.yaxis.labelpad=0;ax.tick_params(axis='y',length=1.8,width=.5,pad=1);ax.tick_params(axis='x',length=0,pad=2)
            if category=='overall':plt.setp(ax.get_xticklabels(),rotation=50,ha='right',rotation_mode='anchor')
            style(ax);save(fig,out/'scenarios'/category,key)
    fig=plt.figure(figsize=(492/72.27,15/72.27))
    fig.legend(handles,['Real baseline','Sim + AWGN'],loc='center',ncol=2,frameon=False,handlelength=2,columnspacing=2)
    save(fig,out/'scenarios','shared_legend')
    # Measured-background examples: rainy Traj-1 Back (134), BS22 (58).
    all_methods=methods+['Real background + Statistics'];colors=['#BCD6ED','#C5DFB4','#F8CAAC']
    limits=[[.82,2.1,1.30,180],[.82,29,1.30,330]]
    ticks=[[[0,.3,.6],[0,.8,1.6],[0,.5,1],[0,50,100]],[[0,.3,.6],[0,10,20],[0,.5,1],[0,100,200]]]
    for di,domain in enumerate(['Rain1','BS22']):
        for mi,key in enumerate(metrics):
            rows=[next(r for r in background if r['domain']==domain and r['method']==m and r['metric']==key) for m in all_methods]
            mean=np.array([r['mean'] for r in rows]);sd=np.array([r['sample_sd'] for r in rows]);x=np.arange(3)
            w,h=120,68;fig=plt.figure(figsize=(w/72.27,h/72.27));ax=fig.add_axes([25/w,8/h,70/w,49/h])
            ax.bar(x,mean,color=colors,width=.55,edgecolor='black',linewidth=.55,zorder=3)
            ax.errorbar(x,mean,yerr=sd,fmt='none',ecolor='black',elinewidth=.55,capsize=1.5,capthick=.55,zorder=4)
            ax.set(xlim=(-.65,2.65),ylim=(0,limits[di][mi]),xticks=[],yticks=ticks[di][mi]);style(ax)
            ax.tick_params(length=2,width=.5,pad=2)
            for i,(v,s) in enumerate(zip(mean,sd)):
                ax.annotate(f'{v:.2f}' if key=='mae' else f'{v:.3f}',(i,v+s),xytext=(0,3),textcoords='offset points',
                    ha='center',va='bottom',fontsize=6.75*u,bbox=dict(facecolor='white',edgecolor='none',pad=.12),zorder=6)
            save(fig,out/'background',f'{domain.lower()}_{key}')
    fig=plt.figure(figsize=(492/72.27,15/72.27))
    fig.legend([Patch(facecolor=c,edgecolor='black',linewidth=.55) for c in colors],
        ['Real','Sim+AWGN','Sim+measured BG'],loc='center',ncol=3,frameon=False,handlelength=.9,columnspacing=1.4)
    save(fig,out/'background','shared_legend')
