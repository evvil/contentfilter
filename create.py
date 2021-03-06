#!/usr/bin/env python

####################################
# 
# Module to create a large json file with lists of
# restricted-content sites
#
# To run this:
#  python create.py

####################################
#Types of restricted sites
# - Adult / Pornographic
# - Weapons
# - Drugs
# - Gambling
# - Gore/Violence
# - Alcohol
# - Cult (e.g. Scientology)
# - Terrorism recruitment (e.g. AlQaeda)

####################################
# Sources:
# - Alexa content ratings
# - DMOZ categories
# - JTerry Content Verification List
# - DomainAnalysis
# - TLDs (.xxx)
# - UNT List
# - Domain name matching

from json import dumps
from datetime import datetime
from os import listdir
from base64 import b64encode
from md5 import new as md5new

from pymongo import MongoClient
from tldextract import extract

#Accessing particular data sources

def category_chunk(c, chunks, negative=False):
	"""Searches for domains by matching specific chunks in their
	DMOZ categories.
	Accepts a Connection (c) and an iterable (chunks)
	Returns """
	
	chunks = set(chunks)
	domains = []
	query = {'alexa.DMOZ.SITE.CATS.CAT':{'$exists':True}}
	requirement = {'domain':1, 'alexa.DMOZ.SITE.CATS.CAT':1}
	
	for domain in c['domains'].find(query, requirement):
		negative_flag = False
		try:
			cat_container = domain['alexa']['DMOZ']['SITE']['CATS']['CAT'] #urgh this API
			if cat_container != {}:
				if type(cat_container) == list:
					cats = [x['@ID'] for x in cat_container] #data consistency, anyone?
				else:
					cats = [cat_container['@ID']]
				
				if negative:
					for cat in cats: #pretty inefficient but gets the job done
						cat = set(cat.split('/'))							
						if negative.intersection(cat):
							negative_flag = True
				
				if not negative_flag:
					for cat in cats:
						cat = cat.split('/')
						for chunk in cat:
							if chunk in chunks:
								domain_name = domain['domain'].replace('#', '.')
								domains.append(domain_name)
								break
		except KeyError:
			continue
	
	return domains

def check_domain_analysis(category):
	"""Domain Analysis is a large spreadsheet with about 1000 several hand classified domains"""
	domains = []
	
	with open('sources/hand_classified/domain_analysis.tsv') as f:
		for line in f:
			line = line.split('\t')
			domain = line[0]
			categories = line[1]
			if category in categories:
				domains.append(domain)
	
	return domains

def load_alexa():
	"""Returns a set of all the domains in the latest Alexa top 1m list"""
	timestamp = datetime.strftime(datetime.now(), '%Y-%m-%d')
	top_1m_location = "/Users/mruttley/Documents/2015-04-22 AdGroups/Bucketerer/data_crunching/ranking_files/"+timestamp+"top-1m.csv"
	alexa = set()
	with open(top_1m_location) as f:
		for n, line in enumerate(f):
			if len(line) > 4:
				if line.endswith('\n'):
					line = line[:-1]
				domain = line.lower().split(',')[1]
				alexa.update([domain])
	return alexa

def prepare_comscore_lists():
	"""Cleans and prepares comscore lists. Only returns files that are in the
	latest Alexa top 1m sites"""
	
	#setup
	directory = 'sources/comscore/'
	alexa = load_alexa() #import alexa
	
	#import each list
	for filename in listdir(directory):
		if filename.endswith("dump") == False:
			print "Working on {0}".format(filename)
			domains = set()
			category = filename.split(".")[0] #filenames are in the format: category.txt
			exists = 0
			
			with open(directory + filename) as f:
				for n, line in enumerate(f):
					line = line.lower()
					if len(line) > 4:
						if line.endswith('\n'):
							line = line[:-1]
						if line.endswith("*"):
							line = line[:-1]
						if " " not in line:
							domains.update([line])
						
			print "Checking against Alexa"
			with open(directory + category + '.dump', 'w') as g:
				for domain in domains:
					if domain in alexa:
						exists += 1
						g.write(domain + "\n")
			
			print "Wrote {0} domains to {1}{2}.dump".format(exists, directory, category)

#Checkers

def check_toulouse_list():
	"""A university in Toulouse provides a gigantic blacklist: http://dsi.ut-capitole.fr/blacklists/index_en.php.
	This checks the latest alexa top 1m against it. Requires two files (see first few lines)
	"""
	
	payload_directory = "sources/toulouse/adult/"
	payload_fn = "domain"
	
	domains = set()
	alexa = load_alexa()
	exists = 0
	
	with open(payload_directory + payload_fn) as f:
		with open('toulouse_check.dump', 'w') as g:
			print "Importing Toulouse payload"
			for n, line in enumerate(f):
				if len(line) > 4: #some weird line ending stuff
					if line.endswith('\n'):
						line = line[:-1]
					domain_info = extract(line)
					if domain_info.subdomain == "":
						domain_name = domain_info.domain + "." + domain_info.suffix
						if domain_name in alexa:
							g.write(domain_name + "\n")
							exists += 1
	
	print "{0} found in Alexa. Written to toulouse_check.dump".format()

#Handlers for each genre

def get_adult_sites():
	"""Gets adult sites from various data sources"""

	domains = set()
	
	#Get sites from bucketerer db
	db_sites = category_chunk(c, ["Adult"])
	domains.update(db_sites)
	
	#get sites from DomainAnalysis
	domain_analysis = check_domain_analysis('18')
	domains.update(domain_analysis)
	
	#get sites by tld
	for domain in c['domains'].find({}, {'domain':1}):
		if domain['domain'].endswith('xxx'):
			domains.update([domain['domain'].replace('#', '.')])
	
	#get comscore sites
	with open('sources/comscore/adult.dump') as f:
		for line in f:
			if len(line) > 4:
				if line.endswith('\n'):
					line = line[:-1]
				domains.update([line])
	
	return sorted(list(domains))

def get_gambling_sites():
	"""Gets gambling sites"""
	
	domains = set()
	
	#get domains from the bucketerer database
	matchers = [
		'Poker', 'Gambling', 'Blackjack'
	]
	dbdomains = category_chunk(c, matchers)
	domains.update(dbdomains)
	
	return sorted(list(domains))

def get_drugs_sites():
	"""Gets drugs sites"""
	
	domains = set()
	
	#get domains from the bucketerer database
	matchers = [
		"Drugs"
	]
	dbdomains = category_chunk(c, matchers)
	domains.update(dbdomains)
	
	with open("sources/suggested/drugs.txt") as f:
		for line in f:
			if len(line) > 4:
				if line.endswith('\n'):
					line = line[:-1]
				domains.update([line])
	
	#remove known false positives
	fps = ["fungi.com"]
	for x in fps:
		if x in domains:
			domains.remove(x)
	
	return sorted(list(domains))

def get_alcohol_sites():
	"""Gets alcohol related sites"""
	
	domains = set()
	
	#get domains from the bucketerer database
	matchers = [
		"Wine", "Beer", "Liquor"
	]
	
	
	negative = ["DOS_and_Windows"]
	negative = set([unicode(x) for x in negative])
	
	dbdomains = category_chunk(c, matchers, negative=negative)
	domains.update(dbdomains)
	
	return sorted(list(domains))	

def create_base64_version(sites):
	"""Creates a base64 version"""
	
	blacklist = []
	for category, domains in sites.iteritems():
		for domain in domains:
			blacklist.append(b64encode(domain))
	
	blacklist.append(b64encode('example.com')) #specific request
	
	return {'domains': blacklist}

def create_md5_version(sites):
	"""Creates an md5 version"""
	
	blacklist = []
	for category, domains in sites.iteritems():
		for domain in domains:
			blacklist.append(md5new(domain).hexdigest())
	
	blacklist.append(md5new('example.com').hexdigest()) #specific request
	
	return {'domains': blacklist}

def create_md5_b64_version(sites):
	"""Creates a version with both hashing methods"""
	
	blacklist = []
	for category, domains in sites.iteritems():
		for domain in domains:
			blacklist.append(b64encode(md5new(domain).digest()))
	
	blacklist.append(b64encode(md5new('example.com').digest())) #specific request
	
	return {'domains': blacklist}

#Main Handler
if __name__ == "__main__":
	#Set up database connection
	c = MongoClient()['bucketerer']
	
	#container
	sites = {}
	
	#prepare comscore stuff
	prepare_comscore_lists()
	
	#get sites from each genre we're concerned about
	print "Processing Adult Sites"; sites['adult'] = get_adult_sites()
	print "Processing Gambling Sites"; sites['gambling'] = get_gambling_sites()
	print "Processing Drugs Sites"; sites['drugs'] = get_drugs_sites()
	print "Processing Alcohol Sites"; sites['alcohol'] = get_alcohol_sites()
	
	#dump b64 encoded version to file
	with open('sitesb64.json', 'w') as f:
		b64 = dumps(create_base64_version(sites), indent=4)
		f.write(b64)
	
	#dump md5 encoded version to file
	with open('md5.json', 'w') as f:
		md5 = dumps(create_md5_version(sites), indent=4)
		f.write(md5)
	
	#dump double encoded version to file
	with open('md5_b64.json', 'w') as f:
		both = dumps(create_md5_b64_version(sites), indent=4)
		f.write(both)
	
	#dump plaintext version to json file
	with open('sites.json', 'w') as f:
		sites= dumps(sites, indent=4)
		f.write(sites)
