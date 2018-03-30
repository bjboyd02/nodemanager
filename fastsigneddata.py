""" Justin Cappos -- routines that create and verify signatures and prevent
replay / freeze / out of sequence / misdelivery attacks

Replay attack:   When someone provides information you signed before to try
to get you to perform an old action again.   For example, A sends messages to
the node manager to provide a vessel to B (B intercepts this traffic).   Later 
A acquires the vessel again.   B should not be able to replay the messages A 
sent to the node manager to have the vessel transferred to B again.

Freeze attack:   When an attacker can act as a man-in-the-middle and provide
stale information to an attacker.   For example, B can intercept all traffic
between the node manager and A.   If C makes a change on the node manager, then
B should not be able to prevent A from seeing the change (at least within 
some time bound).

Out of sequence attack:   When someone can skip sending some messages but
deliver others.   For example, A wants to stop the current program, upload
a new copy of the program, and start the program again.   It should be possible
for A to specify that these actions must be performed in order and without 
skipping any of the prior actions (regardless of failures, etc.).

Misdelivery attack:   Messages should only be acted upon by the nodes that 
the user intended.   A malicious party should not be able to "misdeliver" a
message and have a different node perform the action.



I have support for "sequence numbers" which will require that intermediate 
events are not skipped.    The sequence numbers are a tuple: (tag, version)

"""

# JAC: SHA is really, really slow in Python (#971).   We'll use the Python
# version here...
#include sha.r2py

# Should filter out a warning about sha deprecation (if applicable)
import warnings

# Hide the DeprecationWarning for sha 
warnings.simplefilter('ignore') 
import sha as fastsha
warnings.resetwarnings() 

def sha_hash(data):
  return fastsha.new(data).digest()

from repyportability import *
_context = locals()
add_dy_support(_context)

dy_import_module_symbols("rsa.r2py")
dy_import_module_symbols("time.r2py")


LOCAL_MODE = False

# The signature for a piece of data is appended to the end and has the format:
# \n!publickey!timestamp!expirationtime!sequencedata!destination!signature
# The signature is actually the sha hash of the data (including the
# publickey, timestamp, expirationtime, sequencedata and destination) encrypted
# by the private key.



# I'll allow None and any int, long, or float (can be 0 or negative)
def signeddata_is_valid_timestamp(timestamp):
  if timestamp == None:
    return True

  if type(timestamp) is not int and type(timestamp) is not long and type(timestamp) is not float:
    return False

  return True

  
# I'll allow None and any int, long, or float that is 0 or positive
def signeddata_is_valid_expirationtime(expirationtime):
  if expirationtime == None:
    return True

  if type(expirationtime) is not int and type(expirationtime) is not long and type(expirationtime) is not float:
    return False

  if expirationtime < 0:
    return False

  return True





# sequence numbers must be 'tag:num' where tag doesn't contain ':','\n', or '!' # and num is a number
def signeddata_is_valid_sequencenumber(sequencenumber):
  if sequencenumber == None:
    return True

  if type(sequencenumber) != tuple:
    return False

  if len(sequencenumber) != 2:
    return False

  if type(sequencenumber[0]) != str:
    return False
  
  if '!' in sequencenumber[0] or ':' in sequencenumber[0] or '\n' in sequencenumber[0]:
    return False

  if type(sequencenumber[1]) != long and type(sequencenumber[1]) != int:
    return False

  return True

# Destination is an "opaque string" or None.  Should not contain a '!' or '\n'
def signeddata_is_valid_destination(destination):
  if type(destination) == type(None):
    return True

  # a string without '!' or '\n' ('!' is the separator character, '\n' is not
  # allowed anywhere in the signature)
  if type(destination) == type('abc') and '!' not in destination and '\n' not in destination:
    return True

  return False
  


#applies a signature to a given message (parameter data) and returns the signed message
def signeddata_signdata(data, privatekey, publickey, timestamp=None, expiration=None, sequenceno=None,destination=None):

  if not signeddata_is_valid_timestamp(timestamp):
    raise ValueError, "Invalid Timestamp"

  if not signeddata_is_valid_expirationtime(expiration):
    raise ValueError, "Invalid Expiration Time"

  if not signeddata_is_valid_sequencenumber(sequenceno):
    raise ValueError, "Invalid Sequence Number"

  if not signeddata_is_valid_destination(destination):
    raise ValueError, "Invalid Destination"


  # Build up \n!pubkey!timestamp!expire!sequence!dest!signature
  totaldata = data + "\n!"+rsa_publickey_to_string(publickey)
  totaldata = totaldata+"!"+signeddata_timestamp_to_string(timestamp)
  totaldata = totaldata+"!"+signeddata_expiration_to_string(expiration)
  totaldata = totaldata+"!"+signeddata_sequencenumber_to_string(sequenceno)
  totaldata = totaldata+"!"+signeddata_destination_to_string(destination)
  
  #generate the signature
  signature = signeddata_create_signature(totaldata, privatekey, publickey)
  
  totaldata = totaldata+"!"+ signature

  return totaldata

#creates a signature for the given data string and returns it
def signeddata_create_signature(data, privatekey, publickey):

  # NOTE: This takes waaaay too long.   I'm going to do something simpler...
  #  if not rsa_is_valid_privatekey(privatekey):
  #    raise ValueError, "Invalid Private Key"
  if not privatekey:
    raise ValueError, "Invalid Private Key"
      
  if not rsa_is_valid_publickey(publickey):
    raise ValueError, "Invalid Public Key"
    
  # Time to get the hash...
  hashdata = sha_hash(data)

  # ...and sign it
  signature = rsa_sign(hashdata, privatekey)
  
  return str(signature)


# return [original data, signature]
def signeddata_split_signature(data):
  return data.rsplit('\n',1)


# checks the signature.   If the public key is specified it must match that in
# the file...
def signeddata_issignedcorrectly(data, publickey=None):
  # I'll check signature over all of thesigneddata
  try:
    thesigneddata, signature = data.rsplit('!',1)
    junk, rawpublickey, junktimestamp, junkexpiration, junksequenceno, junkdestination = thesigneddata.rsplit('!',5)
  except ValueError:
    # error splitting the data means it isn't valid...
    return False
  
  if publickey != None and rsa_string_to_publickey(rawpublickey) != publickey:
    return False

  publickey = rsa_string_to_publickey(rawpublickey)

  try: 
    # extract the hash from the signature
    signedhash = rsa_verify(signature, publickey)
  except TypeError, e:
    if 'RSA' not in str(e):
      raise
    # Bad signature or public key
    return False
  except OverflowError, e:      
    #bad signature 
    #this is most likely caused by mismatched public and private keys.
    return False
    
  # Does the hash match the signed data?
  if signedhash == sha_hash(thesigneddata):
    return True
  else:
    return False
  

def signeddata_string_to_destination(destination):
  if destination == 'None':
    return None
  return destination

def signeddata_destination_to_string(destination):
  return str(destination)


def signeddata_string_to_timestamp(rawtimestamp):
  if rawtimestamp == 'None':
    return None
  return float(rawtimestamp)


def signeddata_timestamp_to_string(timestamp):
  return str(timestamp)

def signeddata_string_to_expiration(rawexpiration):
  if rawexpiration == 'None':
    return None
  return float(rawexpiration)

def signeddata_expiration_to_string(expiration):
  return str(expiration)



def signeddata_string_to_sequencenumber(sequencenumberstr):
  if sequencenumberstr == 'None' or sequencenumberstr == None:
    return None

  if type(sequencenumberstr) is not str:
    raise ValueError, "Invalid sequence number type '"+str(type(sequencenumberstr))+"' (must be string)"
    
  if len(sequencenumberstr.split(':')) != 2:
    raise ValueError, "Invalid sequence number string (does not contain 1 ':')"

  if '!' in sequencenumberstr:
    raise ValueError, "Invalid sequence number data: '!' not allowed"
  
  return sequencenumberstr.split(':')[0],int(sequencenumberstr.split(':')[1])


def signeddata_sequencenumber_to_string(sequencenumber):
  if type(sequencenumber) is type(None):
    return 'None'

  if type(sequencenumber[0]) is not str:
    raise ValueError, "Invalid sequence number type"

  if type(sequencenumber[1]) is not long and type(sequencenumber[1]) is not int:
    raise ValueError, "Invalid sequence number count type"
    
  if len(sequencenumber) != 2:
    raise ValueError, "Invalid sequence number"

  return sequencenumber[0]+":"+str(sequencenumber[1])


def signeddata_iscurrent(expiretime):
  if expiretime == None:
    return True

  # may throw TimeError...
  try:
    if LOCAL_MODE:
      currenttime = time_local_gettime()
    else:
      currenttime = time_gettime()
  except TimeError:
    if LOCAL_MODE:
      time_local_updatetime(10000)
      currenttime = time_local_gettime()
    else:
      time_updatetime(34612)
      currenttime = time_gettime()

  if expiretime > currenttime:
    return True
  else:
    return False




def signeddata_has_good_sequence_transition(oldsequence, newsequence):
  # None is always allowed by any prior sequence
  if newsequence == None:
    return True
    
  #newsequence is a tuple
  newsequencename,st_newsequenceno = newsequence
  newsequenceno = int(st_newsequenceno)

  if oldsequence == None: 
    # is this the start of a sequence when there was none prior?
    if newsequenceno == 0:
      return True
    return False
  
  # oldsequence is a pair.
  oldsequencename,st_oldsequenceno = oldsequence
  oldsequenceno = int(st_oldsequenceno)
  

  
  # They are from the same sequence
  if oldsequencename == newsequencename:
    # and this must be the next number to be valid
    if oldsequenceno + 1 == newsequenceno:
      return True
    return False

  else: 
    # Different sequences
 
    # is this the start of a new sequence?
    if newsequenceno == 0:
      return True

    # otherwise this isn't good
    return False


# used in lieu of a global for destination checking
signeddata_identity = {}

# Used to set identity for destination checking...
def signeddata_set_identity(identity):
  signeddata_identity['me'] = identity


def signeddata_destined_for_me(destination):
  # None means it's for everyone
  if destination == None:
    return True

  # My identity wasn't set and the destination was, so fail...
  if 'me' not in signeddata_identity:
    return False

  # otherwise, am I in the colon delimited list?
  if signeddata_identity['me'] in destination.split(':'):
    return True
  return False



def signeddata_split(data):
  originaldata, rawpublickey, rawtimestamp, rawexpiration, rawsequenceno,rawdestination, junksignature = data.rsplit('!',6)
  
  # strip the '\n' off of the original data...
  return originaldata[:-1], rsa_string_to_publickey(rawpublickey), signeddata_string_to_timestamp(rawtimestamp), signeddata_string_to_expiration(rawexpiration), signeddata_string_to_sequencenumber(rawsequenceno), signeddata_string_to_destination(rawdestination)



def signeddata_getcomments(signeddata, publickey=None):
  """Returns a list of problems with the signed data (but doesn't look at sequence number or timestamp data)."""
  returned_comments = []

  try:
    junkdata, pubkey, timestamp, expiretime, sequenceno, destination = signeddata_split(signeddata)
  except KeyError:
    return ['Malformed signed data']

  if publickey != None and publickey != pubkey:
    returned_comments.append('Different public key')

  if not signeddata_issignedcorrectly(signeddata, publickey):
    returned_comments.append("Bad signature")
  
  try:
    if not signeddata_iscurrent(expiretime):
      returned_comments.append("Expired signature")
  except TimeError:
    returned_comments.append("Cannot check expiration")

  #BUG FIX: destination checking has been re-enabled since teh issue with identities not being stored correctly has been fixed
  if destination != None and not signeddata_destined_for_me(destination):
    returned_comments.append("Not destined for this node")


  return returned_comments



signeddata_warning_comments = [ 'Timestamps match', "Cannot check expiration" ]
signeddata_fatal_comments = ['Malformed signed data', 'Different public key', "Bad signature", "Expired signature", 'Public keys do not match', 'Invalid sequence transition', 'Timestamps out of order', 'Not destined for this node']

signeddata_all_comments = signeddata_warning_comments + signeddata_fatal_comments

def signeddata_shouldtrustmeta(oldsignature, newsigneddata, publickey=None):
  """
  the signature of the metadata should be specified for the oldsignature parameter
  newsigneddata must contain the full request,
  """
  return signeddata_shouldtrust(oldsignature, newsigneddata, publickey=None, oldsigneddata_is_fullrequest=False)

def signeddata_shouldtrust(oldsigneddata, newsigneddata, publickey=None, oldsigneddata_is_fullrequest=True):
  """ Returns False for 'don't trust', None for 'use your discretion' and True 
  for everything is okay.   The second item in the return value is a list of
  reasons / justifications
  newsigneddata must contain full request
  by default, oldsigneddata must contain only the full previous request (for compatibility issues).
  if oldsigneddata_is_fullrequest=False, only the signature must be specified for oldsigneddata
  """

  returned_comments = []

# we likely only want to keep the signature data around in many cases.   For 
# example, if the request is huge.   
#  if not signeddata_issignedcorrectly(oldsigneddata, publickey):
#    raise ValueError, "Old signed data is not correctly signed!"

  if not signeddata_issignedcorrectly(newsigneddata, publickey):
    returned_comments.append("Bad signature")
    return False, returned_comments
    
  # extract information about the current signature
  newjunk, newpubkey, newtime, newexpire, newsequence, newdestination = signeddata_split(newsigneddata)
  
  # get comments on everything but the timestamp and sequence number
  returned_comments = returned_comments + signeddata_getcomments(newsigneddata, publickey)
  
  #BUG FIX: only if the oldmetadata is not set to None, we want to split it and verify it
  if oldsigneddata != None :
  
    if (oldsigneddata_is_fullrequest):
      oldjunk, oldpubkey, oldtime, oldexpire, oldsequence, olddestination = signeddata_split(oldsigneddata)
    else:
      oldrawpublickey, oldrawtimestamp, oldrawexpiration, oldrawsequenceno, oldrawdestination, oldjunksignature = oldsigneddata.rsplit('!',5)
      oldpubkey, oldtime, oldexpire, oldsequence, olddestination = rsa_string_to_publickey(oldrawpublickey[1:]), signeddata_string_to_timestamp(oldrawtimestamp), signeddata_string_to_expiration(oldrawexpiration), signeddata_string_to_sequencenumber(oldrawsequenceno), signeddata_string_to_destination(oldrawdestination)
    
  

    # get comments on everything but the timestamp and sequence number
    returned_comments = returned_comments + signeddata_getcomments(newsigneddata, publickey)
  
    # check the sequence number data...
    if not signeddata_has_good_sequence_transition(oldsequence, newsequence):
      returned_comments.append('Invalid sequence transition')

    # check the timestamps...  
    if (newtime == None and oldtime != None) or oldtime == None or oldtime > newtime:
      # if the timestamps are reversed (None is the earliest possible)
      returned_comments.append('Timestamps out of order')
    elif oldtime != None and newtime != None and oldtime == newtime:
      # the timestamps are equal but not none...
      returned_comments.append('Timestamps match')
    else:   # So they either must both be None or oldtime < newtime
      assert((newtime == oldtime == None) or oldtime < newtime)
  

  # let's see what happened...
  if returned_comments == []:
    return True, []
  for comment in returned_comments:
    if comment in signeddata_fatal_comments:
      return False, returned_comments

    # if not a failure, should be a warning comment
    assert(comment in signeddata_warning_comments)

  # Warnings, so I won't return True
  return None, returned_comments
  
