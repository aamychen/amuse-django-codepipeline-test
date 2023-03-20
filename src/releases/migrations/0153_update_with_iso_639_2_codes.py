from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('releases', '0152_metadatalanguage_iso_639_2')]

    operations = [
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='aar' WHERE iso_639_1='aa';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='abk' WHERE iso_639_1='ab';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='afr' WHERE iso_639_1='af';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='aka' WHERE iso_639_1='ak';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='amh' WHERE iso_639_1='am';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='ara' WHERE iso_639_1='ar';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='arg' WHERE iso_639_1='an';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='asm' WHERE iso_639_1='as';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='ava' WHERE iso_639_1='av';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='ave' WHERE iso_639_1='ae';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='aym' WHERE iso_639_1='ay';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='aze' WHERE iso_639_1='az';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='bak' WHERE iso_639_1='ba';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='bam' WHERE iso_639_1='bm';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='bel' WHERE iso_639_1='be';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='ben' WHERE iso_639_1='bn';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='bih' WHERE iso_639_1='bh';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='bis' WHERE iso_639_1='bi';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='bod' WHERE iso_639_1='bo';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='bos' WHERE iso_639_1='bs';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='bre' WHERE iso_639_1='br';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='bul' WHERE iso_639_1='bg';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='cat' WHERE iso_639_1='ca';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='ces' WHERE iso_639_1='cs';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='cha' WHERE iso_639_1='ch';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='che' WHERE iso_639_1='ce';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='chu' WHERE iso_639_1='cu';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='chv' WHERE iso_639_1='cv';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='cor' WHERE iso_639_1='kw';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='cos' WHERE iso_639_1='co';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='cre' WHERE iso_639_1='cr';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='cym' WHERE iso_639_1='cy';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='dan' WHERE iso_639_1='da';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='deu' WHERE iso_639_1='de';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='div' WHERE iso_639_1='dv';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='dzo' WHERE iso_639_1='dz';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='ell' WHERE iso_639_1='el';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='eng' WHERE iso_639_1='en';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='epo' WHERE iso_639_1='eo';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='est' WHERE iso_639_1='et';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='eus' WHERE iso_639_1='eu';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='ewe' WHERE iso_639_1='ee';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='fao' WHERE iso_639_1='fo';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='fas' WHERE iso_639_1='fa';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='fij' WHERE iso_639_1='fj';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='fin' WHERE iso_639_1='fi';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='fra' WHERE iso_639_1='fr';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='fry' WHERE iso_639_1='fy';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='ful' WHERE iso_639_1='ff';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='gla' WHERE iso_639_1='gd';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='gle' WHERE iso_639_1='ga';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='glg' WHERE iso_639_1='gl';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='glv' WHERE iso_639_1='gv';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='grn' WHERE iso_639_1='gn';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='guj' WHERE iso_639_1='gu';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='hat' WHERE iso_639_1='ht';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='hau' WHERE iso_639_1='ha';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='heb' WHERE iso_639_1='he';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='her' WHERE iso_639_1='hz';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='hin' WHERE iso_639_1='hi';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='hmo' WHERE iso_639_1='ho';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='hrv' WHERE iso_639_1='hr';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='hun' WHERE iso_639_1='hu';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='hye' WHERE iso_639_1='hy';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='ibo' WHERE iso_639_1='ig';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='ido' WHERE iso_639_1='io';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='iii' WHERE iso_639_1='ii';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='iku' WHERE iso_639_1='iu';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='ile' WHERE iso_639_1='ie';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='ina' WHERE iso_639_1='ia';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='ind' WHERE iso_639_1='id';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='ipk' WHERE iso_639_1='ik';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='isl' WHERE iso_639_1='is';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='ita' WHERE iso_639_1='it';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='jav' WHERE iso_639_1='jv';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='jpn' WHERE iso_639_1='ja';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='kal' WHERE iso_639_1='kl';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='kan' WHERE iso_639_1='kn';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='kas' WHERE iso_639_1='ks';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='kat' WHERE iso_639_1='ka';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='kau' WHERE iso_639_1='kr';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='kaz' WHERE iso_639_1='kk';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='khm' WHERE iso_639_1='km';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='kik' WHERE iso_639_1='ki';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='kin' WHERE iso_639_1='rw';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='kir' WHERE iso_639_1='ky';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='kom' WHERE iso_639_1='kv';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='kon' WHERE iso_639_1='kg';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='kor' WHERE iso_639_1='ko';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='kua' WHERE iso_639_1='kj';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='kur' WHERE iso_639_1='ku';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='lao' WHERE iso_639_1='lo';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='lat' WHERE iso_639_1='la';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='lav' WHERE iso_639_1='lv';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='lim' WHERE iso_639_1='li';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='lin' WHERE iso_639_1='ln';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='lit' WHERE iso_639_1='lt';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='ltz' WHERE iso_639_1='lb';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='lub' WHERE iso_639_1='lu';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='lug' WHERE iso_639_1='lg';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='mah' WHERE iso_639_1='mh';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='mal' WHERE iso_639_1='ml';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='mar' WHERE iso_639_1='mr';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='mkd' WHERE iso_639_1='mk';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='mlg' WHERE iso_639_1='mg';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='mlt' WHERE iso_639_1='mt';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='mon' WHERE iso_639_1='mn';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='mri' WHERE iso_639_1='mi';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='msa' WHERE iso_639_1='ms';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='mya' WHERE iso_639_1='my';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='nau' WHERE iso_639_1='na';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='nav' WHERE iso_639_1='nv';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='nbl' WHERE iso_639_1='nr';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='nde' WHERE iso_639_1='nd';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='ndo' WHERE iso_639_1='ng';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='nep' WHERE iso_639_1='ne';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='nld' WHERE iso_639_1='nl';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='nno' WHERE iso_639_1='nn';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='nob' WHERE iso_639_1='nb';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='nor' WHERE iso_639_1='no';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='nya' WHERE iso_639_1='ny';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='oci' WHERE iso_639_1='oc';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='oji' WHERE iso_639_1='oj';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='ori' WHERE iso_639_1='or';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='orm' WHERE iso_639_1='om';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='oss' WHERE iso_639_1='os';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='pan' WHERE iso_639_1='pa';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='pli' WHERE iso_639_1='pi';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='pol' WHERE iso_639_1='pl';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='por' WHERE iso_639_1='pt';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='pus' WHERE iso_639_1='ps';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='que' WHERE iso_639_1='qu';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='roh' WHERE iso_639_1='rm';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='ron' WHERE iso_639_1='ro';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='run' WHERE iso_639_1='rn';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='rus' WHERE iso_639_1='ru';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='sag' WHERE iso_639_1='sg';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='san' WHERE iso_639_1='sa';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='sin' WHERE iso_639_1='si';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='slk' WHERE iso_639_1='sk';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='slv' WHERE iso_639_1='sl';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='sme' WHERE iso_639_1='se';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='smo' WHERE iso_639_1='sm';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='sna' WHERE iso_639_1='sn';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='snd' WHERE iso_639_1='sd';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='som' WHERE iso_639_1='so';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='sot' WHERE iso_639_1='st';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='spa' WHERE iso_639_1='es';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='sqi' WHERE iso_639_1='sq';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='srd' WHERE iso_639_1='sc';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='srp' WHERE iso_639_1='sr';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='ssw' WHERE iso_639_1='ss';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='sun' WHERE iso_639_1='su';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='swa' WHERE iso_639_1='sw';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='swe' WHERE iso_639_1='sv';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='tah' WHERE iso_639_1='ty';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='tam' WHERE iso_639_1='ta';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='tat' WHERE iso_639_1='tt';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='tel' WHERE iso_639_1='te';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='tgk' WHERE iso_639_1='tg';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='tgl' WHERE iso_639_1='tl';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='tha' WHERE iso_639_1='th';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='tir' WHERE iso_639_1='ti';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='ton' WHERE iso_639_1='to';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='tsn' WHERE iso_639_1='tn';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='tso' WHERE iso_639_1='ts';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='tuk' WHERE iso_639_1='tk';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='tur' WHERE iso_639_1='tr';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='twi' WHERE iso_639_1='tw';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='uig' WHERE iso_639_1='ug';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='ukr' WHERE iso_639_1='uk';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='urd' WHERE iso_639_1='ur';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='uzb' WHERE iso_639_1='uz';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='ven' WHERE iso_639_1='ve';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='vie' WHERE iso_639_1='vi';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='vol' WHERE iso_639_1='vo';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='wln' WHERE iso_639_1='wa';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='wol' WHERE iso_639_1='wo';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='xho' WHERE iso_639_1='xh';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='yid' WHERE iso_639_1='yi';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='yor' WHERE iso_639_1='yo';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='zha' WHERE iso_639_1='za';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='zho' WHERE iso_639_1='zh';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='zul' WHERE iso_639_1='zu';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='zxx' WHERE fuga_code='zxx';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='cpe' WHERE fuga_code='cpe';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='cpf' WHERE fuga_code='cpf';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='cpp' WHERE fuga_code='cpp';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='mag' WHERE fuga_code='mag';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='mai' WHERE fuga_code='mai';'''
        ),
        migrations.RunSQL(
            '''UPDATE releases_metadatalanguage SET iso_639_2='bho' WHERE fuga_code='bho';'''
        ),
    ]
